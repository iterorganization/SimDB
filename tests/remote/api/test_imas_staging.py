"""The IMAS URI rewritten at ingestion must point at the staged directory.

Each IMAS file is staged individually through ``secure_path(..., is_file=True)``,
which sanitises only the file name and leaves the directories above it alone. The
URI stored for the simulation names that directory, so it has to be resolved with
``is_file=False`` -- resolving it as a file sanitises the directory's own name and
points the URI at somewhere nothing was ever written.
"""

import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from conftest import HEADERS, TEST_PASSWORD, has_flask, post_simulation

from simdb.config import Config
from simdb.imas.utils import SimDBUrl
from simdb.remote.app import create_app
from simdb.remote.models import FileData, SimulationData, SimulationPostData

IMAS_HOST = "imas.test"

# secure_filename() rewrites this to "run_1", so the file and directory forms of
# secure_path() disagree unless the directory is resolved as a directory.
IMAS_DIR = "/data/sim/run 1"
SIBLING_DIR = "/data/sim/other"


@pytest.fixture
def client_imas_remote():
    if not has_flask:
        pytest.skip("Flask not installed")
    config = Config()
    config.load()
    db_fd, db_file = tempfile.mkstemp()
    upload_dir = tempfile.mkdtemp()
    config.set_option("database.type", "sqlite")
    config.set_option("database.file", db_file)
    config.set_option("server.admin_password", TEST_PASSWORD)
    config.set_option("server.upload_folder", upload_dir)
    config.set_option("authentication.type", "None")
    config.set_option("server.copy_files", True)
    config.set_option("server.imas_remote_host", IMAS_HOST)
    config.set_option("role.admin.users", "admin,admin2")
    app = create_app(config=config, testing=True, debug=True)
    app.testing = True

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    Path(db_file).unlink()
    shutil.rmtree(upload_dir)


def _imas_file(path: str) -> FileData:
    return FileData(
        type="IMAS",
        uri=f"imas:hdf5?path={path}",
        checksum="fake_checksum",
        datetime=datetime.now(timezone.utc),
    )


def test_staged_imas_uri_keeps_the_directory_name(client_imas_remote):
    # Two IMAS directories so that they have a common root to stage relative to.
    simulation = SimulationData(
        alias=uuid.uuid4().hex,
        inputs=[_imas_file(IMAS_DIR), _imas_file(SIBLING_DIR)],
    )
    data = SimulationPostData(simulation=simulation, add_watcher=False)

    rv = post_simulation(client_imas_remote, data)
    assert rv.status_code == 200
    sim_uuid = rv.json["ingested"]

    rv = client_imas_remote.get(f"/v1.2/simulation/{sim_uuid}", headers=HEADERS)
    assert rv.status_code == 200

    staging_dir = (
        Path(
            client_imas_remote.application.simdb_config.get_string_option(
                "server.upload_folder"
            )
        )
        / sim_uuid
    )
    staged = {
        dict(SimDBUrl(file["uri"]).query_params())["path"] for file in rv.json["inputs"]
    }
    assert staged == {
        str(staging_dir / "run 1"),
        str(staging_dir / "other"),
    }


def test_a_traversing_imas_path_is_refused(client_imas_remote):
    """A path that would stage outside the upload folder is a client error.

    os.path.commonpath treats ".." as an ordinary segment, so it reports
    "/data/sim" as the common root of these two and the escape survives into the
    path the URI would point at.
    """
    simulation = SimulationData(
        alias=uuid.uuid4().hex,
        inputs=[_imas_file("/data/sim/../../../etc/pwned"), _imas_file(SIBLING_DIR)],
    )
    data = SimulationPostData(simulation=simulation, add_watcher=False)

    rv = post_simulation(client_imas_remote, data)

    assert rv.status_code == 400
    assert "escapes" in rv.json["error"]
