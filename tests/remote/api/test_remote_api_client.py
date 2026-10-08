"""Round-trip tests for the CLI RemoteAPI client against the real server.

The client talks to the Flask test client instead of the network, so every
request body, query parameter and response is validated by the pydantic models
of both sides.
"""

import base64
import gzip
import io
import json
import os
import shutil
import tempfile
from functools import partial
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

import pytest
from conftest import TEST_PASSWORD, has_flask

from simdb.cli.manifest import Manifest
from simdb.cli.remote_api import FailedConnection, RemoteAPI, RemoteError
from simdb.config import Config
from simdb.database.models import Simulation
from simdb.notifications import Notification
from simdb.remote.app import create_app
from simdb.remote.models import (
    SimulationDeleteResponse,
    SimulationTraceData,
    UploadOptions,
    WatcherData,
)

REMOTE_URL = "http://remote.test"

VALIDATION_SCHEMA = """\
status:
  type: string
"""


class _Response:
    """The parts of a requests.Response the RemoteAPI uses."""

    def __init__(self, response, url):
        self.status_code = response.status_code
        self.headers = response.headers
        self.url = url
        content = response.data
        if (response.headers.get("Content-Encoding") or "").lower() == "gzip":
            # requests transparently decodes this for the real client
            content = gzip.decompress(content)
        self.content = content

    def json(self, **kwargs):
        return json.loads(self.content.decode(), **kwargs)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code} for {self.url}")

    def iter_content(self, chunk_size=1):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start : start + chunk_size]


def _requests_shim(client):
    """Return a stand-in for the requests module routed to *client*."""

    def request(
        method,
        url,
        params=None,
        data=None,
        headers=None,
        auth=None,
        files=None,
        **_kwargs,
    ):
        path = url[len(REMOTE_URL) :]
        query = None
        if "?" in path:
            path, _, query = path.partition("?")
        if params:
            extra = urlencode(params, doseq=True)
            query = f"{query}&{extra}" if query else extra

        body = data
        if files:
            fields = {}
            for key, (name, content, _content_type) in files:
                fields.setdefault(key, []).append((io.BytesIO(content), name))
            body = {k: v[0] if len(v) == 1 else v for k, v in fields.items()}

        request_headers = dict(headers or {})
        if isinstance(auth, tuple):
            credentials = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            request_headers["Authorization"] = f"Basic {credentials}"

        return _Response(
            client.open(
                path,
                method=method,
                query_string=query,
                data=body,
                headers=request_headers,
            ),
            url,
        )

    shim = mock.MagicMock()
    for method in ("get", "post", "put", "patch", "delete"):
        shim.configure_mock(**{method: partial(request, method.upper())})
    shim.ConnectionError = ConnectionError
    shim.HTTPError = type("HTTPError", (Exception,), {})
    shim.JSONDecodeError = json.JSONDecodeError
    return shim


@pytest.fixture(scope="function")
def remote(tmp_path):
    """Yield a (RemoteAPI, admin RemoteAPI) pair talking to a live server."""
    if not has_flask:
        pytest.skip("Flask not installed")

    schema_file = tmp_path / "validation.yaml"
    schema_file.write_text(VALIDATION_SCHEMA)

    db_fd, db_file = tempfile.mkstemp()
    upload_dir = tempfile.mkdtemp()

    config = Config()
    config.load()
    config.set_option("database.type", "sqlite")
    config.set_option("database.file", db_file)
    config.set_option("server.admin_password", TEST_PASSWORD)
    config.set_option("server.upload_folder", upload_dir)
    config.set_option("authentication.type", "None")
    config.set_option("server.copy_files", True)
    config.set_option("role.admin.users", "admin")
    config.set_option("validation.path", str(schema_file))
    config.set_option("flask.secret_key", "test-secret")
    app = create_app(config=config, testing=True, debug=True)
    app.testing = True

    client_config = Config()
    client_config.set_option(f"remote.{'test'}.url", REMOTE_URL)

    with app.test_client() as client, mock.patch(
        "simdb.cli.remote_api.requests", _requests_shim(client)
    ):
        api = RemoteAPI("test", None, None, client_config, use_token=False)
        admin = RemoteAPI(
            "test", "admin", TEST_PASSWORD, client_config, use_token=False
        )
        yield api, admin

    os.close(db_fd)
    Path(db_file).unlink()
    shutil.rmtree(upload_dir)


def _push_simulation(api, tmp_path, alias="client-sim"):
    data_file = tmp_path / "input.txt"
    data_file.write_text("hello simdb\n")
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(
        "manifest_version: 2\n"
        f"alias: {alias}\n"
        "inputs:\n"
        f"  - uri: file://{data_file}\n"
        "outputs:\n"
        f"  - uri: file://{data_file}\n"
        "metadata:\n"
        "- values:\n"
        "    code: my-code\n"
    )
    simulation = Simulation(Manifest.load_from_file(manifest_file))
    api.push_simulation(simulation, out_stream=io.StringIO(), add_watcher=False)
    return simulation


def test_index_endpoints(remote):
    api, _ = remote

    assert str(api.version).startswith("1.3")
    assert any(url.endswith("simulations") for url in api.get_endpoints())
    assert api.get_upload_options() == UploadOptions(copy_files=True, copy_ids=True)
    assert isinstance(api.get_directory(), Path)
    assert api.get_validation_schemas() == [{"status": {"type": "string"}}]


def test_token(remote):
    _, admin = remote

    assert admin.get_token()


def test_push_and_get_simulation(remote, tmp_path):
    api, _ = remote

    simulation = _push_simulation(api, tmp_path)
    pushed = api.get_simulation(simulation.uuid.hex)

    assert pushed.uuid == simulation.uuid
    assert pushed.alias == "client-sim"
    assert pushed.meta_dict()["values"]["code"] == "my-code"
    # the file has been staged on the server, so the URI now points there
    assert len(pushed.inputs) == 1
    assert Path(pushed.inputs[0].uri.path).read_text() == "hello simdb\n"


def test_list_and_query_simulations(remote, tmp_path):
    api, _ = remote

    simulation = _push_simulation(api, tmp_path)

    listed = api.list_simulations(limit=0)
    assert [sim.uuid for sim in listed] == [simulation.uuid]

    queried = api.query_simulations(["values.code=my-code"], ["values.code"])
    assert [sim.uuid for sim in queried] == [simulation.uuid]
    assert queried[0].find_meta("values.code") == ["my-code"]

    assert api.query_simulations(["values.code=other"], []) == []


def test_trace_simulation(remote, tmp_path):
    api, _ = remote

    simulation = _push_simulation(api, tmp_path)
    trace = api.trace_simulation(simulation.uuid.hex)

    assert isinstance(trace, SimulationTraceData)
    assert trace.uuid == simulation.uuid
    assert trace.status == "not validated"
    assert trace.replaces is None


def test_validate_simulation(remote, tmp_path):
    api, _ = remote

    simulation = _push_simulation(api, tmp_path)

    assert api.validate_simulation(simulation.uuid.hex) == (True, "")


def test_watchers(remote, tmp_path):
    api, _ = remote

    simulation = _push_simulation(api, tmp_path)
    sim_id = simulation.uuid.hex

    assert api.list_watchers(sim_id) == []

    api.add_watcher(sim_id, "watcher1", "example@iter.org", Notification.ALL)
    assert api.list_watchers(sim_id) == [
        WatcherData(username="watcher1", email="example@iter.org", notification="A")
    ]

    api.remove_watcher(sim_id, "watcher1")
    assert api.list_watchers(sim_id) == []


def test_metadata(remote, tmp_path):
    api, admin = remote

    simulation = _push_simulation(api, tmp_path)
    sim_id = simulation.uuid.hex

    assert admin.set_metadata(sim_id, "code", "first") == []
    assert admin.set_metadata(sim_id, "code", "second") == ["first"]

    assert admin.delete_metadata(sim_id, "code") is None
    assert "code" not in api.get_simulation(sim_id).meta_dict()


def test_update_simulation_status(remote, tmp_path):
    api, admin = remote

    simulation = _push_simulation(api, tmp_path)
    sim_id = simulation.uuid.hex

    admin.update_simulation(sim_id, Simulation.Status.ACCEPTED)

    assert api.get_simulation(sim_id).status == Simulation.Status.ACCEPTED


def test_delete_simulation(remote, tmp_path):
    api, admin = remote

    simulation = _push_simulation(api, tmp_path)

    deleted = admin.delete_simulation(simulation.uuid.hex)

    assert isinstance(deleted, SimulationDeleteResponse)
    assert deleted.deleted.simulation == simulation.uuid
    assert deleted.deleted.files
    assert api.list_simulations() == []


def test_pull_simulation(remote, tmp_path):
    api, _ = remote

    simulation = _push_simulation(api, tmp_path)

    pulled = api.pull_simulation(
        simulation.uuid.hex, tmp_path / "pulled", out_stream=io.StringIO()
    )

    assert pulled.uuid == simulation.uuid
    assert Path(pulled.inputs[0].uri.path).read_text() == "hello simdb\n"


def test_simulation_data_reports_remote_errors(remote, tmp_path):
    """The v1.3 IMAS data endpoint reports errors as a RemoteError, not a model."""
    api, _ = remote

    simulation = _push_simulation(api, tmp_path)

    with pytest.raises(RemoteError):
        # the simulation holds no IMAS data, so the remote reports an error
        api.get_simulation_data(simulation.uuid.hex, "core_profiles/time")


def test_invalid_json_from_remote_is_reported(remote):
    """A non-JSON body is reported as a failed connection, not a pydantic error."""
    api, _ = remote

    with mock.patch.object(
        RemoteAPI, "get", return_value=mock.Mock(content=b"<html>login</html>")
    ), pytest.raises(FailedConnection, match="Invalid JSON"):
        api.get_simulation("does-not-matter")


def test_unexpected_response_from_remote_is_reported(remote):
    """A JSON body that does not match the model is reported as a remote error."""
    api, _ = remote

    with mock.patch.object(
        RemoteAPI, "get", return_value=mock.Mock(content=b'{"unexpected": true}')
    ), pytest.raises(RemoteError, match="Unexpected data exchanged"):
        api.get_simulation("does-not-matter")
