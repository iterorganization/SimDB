import io
from unittest import mock

import pytest

from simdb.cli.manifest import Manifest
from simdb.cli.remote_api import RemoteAPI, RemoteError, select_api_version
from simdb.config import Config
from simdb.database.models import Simulation


def test_selects_highest_common_version():
    assert (
        select_api_version(["v1", "v1.1", "v1.2", "v1.3"], ("v1", "v1.1", "v1.2"))
        == "v1.2"
    )
    assert select_api_version(["v1", "v1.1"], ("v1", "v1.1", "v1.2")) == "v1.1"


def test_no_common_version_returns_none():
    assert select_api_version(["v2"], ("v1", "v1.1", "v1.2")) is None
    assert select_api_version([], ("v1", "v1.1", "v1.2")) is None


def test_versions_compare_semantically_not_lexicographically():
    assert select_api_version(["v1.2", "v1.10"], ("v1.2", "v1.10")) == "v1.10"


def _remote_api(endpoints=("v1.2", "v1.3")):
    config = Config()
    config.set_option("remote.test.url", "http://remote.test")
    config.set_option("remote.test.token", "123ABC")

    with mock.patch.object(
        RemoteAPI, "get_server_authentication", return_value="None"
    ), mock.patch.object(
        RemoteAPI, "get_endpoints", return_value=list(endpoints)
    ), mock.patch.object(
        RemoteAPI, "get_api_version", return_value="1.3"
    ), mock.patch.object(RemoteAPI, "get_server_version", return_value="0.11"):
        return RemoteAPI("test", None, None, config)


def test_requests_use_the_negotiated_version():
    api = _remote_api()

    assert api._api_url == "http://remote.test/v1.3/"


def test_api_version_switches_the_requested_version():
    api = _remote_api()

    with api.api_version("v1.2"):
        assert api._api_url == "http://remote.test/v1.2/"

    assert api._api_url == "http://remote.test/v1.3/"


def test_api_version_not_provided_by_remote_raises():
    api = _remote_api(endpoints=("v1.3",))

    with pytest.raises(RemoteError, match="not provided by remote"), api.api_version(
        "v1.2"
    ):
        pass


def test_api_version_unknown_to_client_raises():
    api = _remote_api()

    with pytest.raises(
        RemoteError, match="not supported by this client"
    ), api.api_version("v1.1"):
        pass


def test_push_simulation_uses_v1_2_when_v1_3_is_negotiated():
    api = _remote_api()
    simulation = Simulation(Manifest())
    used_urls = []

    with mock.patch.object(
        RemoteAPI, "get_upload_options", return_value={"copy_files": False}
    ), mock.patch.object(
        RemoteAPI, "post", side_effect=lambda *a, **kw: used_urls.append(api._api_url)
    ):
        api.push_simulation(simulation, out_stream=io.StringIO())

    assert used_urls == ["http://remote.test/v1.2/"]
    assert api._api_url == "http://remote.test/v1.3/"


def test_push_simulation_requires_v1_2_on_the_remote():
    api = _remote_api(endpoints=("v1.3",))

    with pytest.raises(RemoteError, match=r"requires one of the API versions v1\.2"):
        api.push_simulation(Simulation(Manifest()), out_stream=io.StringIO())
