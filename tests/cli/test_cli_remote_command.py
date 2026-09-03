"""Tests for ``simdb remote``.

The remote handshake is stubbed by the ``remote_handshake`` fixture; each test
stubs only the one API call its command makes.
"""

import uuid
from unittest import mock

import pytest
from cli_helpers import make_simulation

from simdb.cli.remote_api import RemoteAPI
from simdb.database.models.simulation import Simulation
from simdb.notifications import Notification
from simdb.remote.models import SimulationTraceData, WatcherData

pytestmark = pytest.mark.usefixtures("remote_handshake")


@pytest.fixture
def api_call():
    """Stub a single :class:`RemoteAPI` method by name.

    ``api_call("list_simulations", return_value=[...])`` patches the method for
    the duration of the test and hands back the mock to assert on.
    """
    patches = []

    def _api_call(name, **kwargs):
        patcher = mock.patch.object(RemoteAPI, name, **kwargs)
        patches.append(patcher)
        return patcher.start()

    yield _api_call

    for patcher in reversed(patches):
        patcher.stop()


# ---------------------------------------------------------------------------
# remote test / directory
# ---------------------------------------------------------------------------


def test_test_command_reports_the_remote_api_version(invoke, remote_handshake):
    result = invoke("remote", "test")

    assert result.exit_code == 0
    assert "Remote is valid" in result.output
    assert "1.3" in result.output


def test_directory_prints_the_remote_storage_directory(invoke, api_call):
    api_call("get_directory", return_value="/srv/simdb/data")

    result = invoke("remote", "directory")

    assert result.exit_code == 0
    assert "/srv/simdb/data" in result.output


# ---------------------------------------------------------------------------
# remote watcher
# ---------------------------------------------------------------------------


def test_watcher_list_prints_every_watcher(invoke, api_call, remote_handshake):
    watchers = [
        WatcherData(username="a", email="a@simdb.test", notification="A"),
        WatcherData(username="b", email="b@simdb.test", notification="V"),
        WatcherData(username="c", email="c@simdb.test", notification="R"),
    ]
    list_watchers = api_call("list_watchers", return_value=watchers)

    result = invoke("remote", "watcher", "list", "acbd1234")

    assert result.exit_code == 0
    assert "acbd1234" in result.output
    for watcher in watchers:
        assert watcher.username in result.output
        assert watcher.email in result.output
    assert list_watchers.called
    assert remote_handshake.get_api_version.called


def test_watcher_list_reports_no_watchers(invoke, api_call):
    api_call("list_watchers", return_value=[])

    result = invoke("remote", "watcher", "list", "acbd1234")

    assert result.exit_code == 0
    assert "no watchers found for simulation acbd1234" in result.output


def test_watcher_remove_passes_the_user_on(invoke, api_call):
    remove_watcher = api_call("remove_watcher")

    result = invoke("remote", "watcher", "remove", "acbd1234", "--user=test")

    assert result.exit_code == 0
    assert "acbd1234" in result.output
    assert remove_watcher.call_args.args == ("acbd1234", "test")


def test_watcher_remove_fails_without_a_user(invoke, api_call):
    remove_watcher = api_call("remove_watcher")

    result = invoke("remote", "watcher", "remove", "acbd1234")

    assert result.exit_code != 0
    assert not remove_watcher.called


@pytest.mark.xfail(
    strict=True,
    reason=(
        "remove_watcher calls get_string_option('user.name') without default=None, "
        "so the config lookup raises KeyError before its own error message is built"
    ),
)
def test_watcher_remove_explains_a_missing_user(invoke, api_call):
    """``watcher add`` reports this cleanly; ``watcher remove`` should match it."""
    api_call("remove_watcher")

    result = invoke("remote", "watcher", "remove", "acbd1234")

    assert "User not provided and user.name not found in config" in result.output


def test_watcher_add_passes_user_email_and_notification(invoke, api_call):
    add_watcher = api_call("add_watcher")

    result = invoke(
        "remote",
        "watcher",
        "add",
        "acbd1234",
        "--user=test",
        "--email=test@iter.org",
        "--notification=all",
    )

    assert result.exit_code == 0
    assert "acbd1234" in result.output
    assert add_watcher.call_args.args == (
        "acbd1234",
        "test",
        "test@iter.org",
        Notification.ALL,
    )


def test_watcher_add_needs_an_email(invoke, api_call):
    add_watcher = api_call("add_watcher")

    result = invoke("remote", "watcher", "add", "acbd1234", "--user=test")

    assert result.exit_code != 0
    assert "Email not provided and user.email not found in config" in result.output
    assert not add_watcher.called


def test_watcher_add_rejects_an_unknown_notification(invoke, api_call):
    add_watcher = api_call("add_watcher")

    result = invoke(
        "remote", "watcher", "add", "acbd1234", "--user=t", "-e=t@x", "-n=sometimes"
    )

    assert result.exit_code == 2
    assert not add_watcher.called


# ---------------------------------------------------------------------------
# remote list / info / query
# ---------------------------------------------------------------------------


def test_list_prints_the_returned_simulations(invoke, api_call, remote_handshake):
    simulations = [
        make_simulation("test", uuid="abcd1234"),
        make_simulation("test", uuid="abcd5678"),
        make_simulation("test", uuid="abcd4321"),
    ]
    list_simulations = api_call("list_simulations", return_value=simulations)

    result = invoke("remote", "list", "--uuid")

    assert result.exit_code == 0
    for simulation in simulations:
        assert simulation.uuid in result.output
    assert list_simulations.called
    assert remote_handshake.get_api_version.called


def test_list_shows_the_extra_columns_when_verbose(invoke, api_call):
    api_call(
        "list_simulations",
        return_value=[
            make_simulation(
                "test", uuid="abcd1234", datetime="2000-01-01-01", status="passed"
            )
        ],
    )

    result = invoke("--verbose", "remote", "list", "--uuid")

    assert result.exit_code == 0
    assert "2000-01-01-01" in result.output
    assert "passed" in result.output


def test_list_rejects_a_negative_limit(invoke, api_call):
    list_simulations = api_call("list_simulations")

    result = invoke("remote", "list", "--limit=-1")

    assert result.exit_code == 2
    assert not list_simulations.called


def test_info_prints_the_simulation(invoke, api_call):
    get_simulation = api_call("get_simulation", return_value="simulation description")

    result = invoke("remote", "info", "abcd1234")

    assert result.exit_code == 0
    assert "simulation description" in result.output
    assert get_simulation.call_args.args == ("abcd1234",)


def test_query_forwards_the_constraints(invoke, api_call):
    constraints = ("alias=123", "description=in:test")
    query_simulations = api_call(
        "query_simulations", return_value=[make_simulation("123", uuid="abcd1234")]
    )

    result = invoke("remote", "query", "--uuid", *constraints)

    assert result.exit_code == 0
    assert "abcd1234" in result.output
    assert query_simulations.call_args.args == (constraints, (), 100)


def test_query_shows_the_extra_columns_when_verbose(invoke, api_call):
    api_call(
        "query_simulations",
        return_value=[
            make_simulation(
                "123", uuid="abcd1234", datetime="2000-01-01-01", status="passed"
            )
        ],
    )

    result = invoke("--verbose", "remote", "query", "--uuid", "alias=123")

    assert result.exit_code == 0
    assert "2000-01-01-01" in result.output
    assert "passed" in result.output


# ---------------------------------------------------------------------------
# remote version / trace
# ---------------------------------------------------------------------------


def test_version_prints_the_remote_simdb_version(invoke):
    result = invoke("remote", "version")

    assert result.exit_code == 0
    assert "Remote 'test' SimDB version: 0.11" in result.output


def test_trace_prints_the_provenance_chain(invoke, api_call):
    trace_simulation = api_call(
        "trace_simulation",
        return_value=SimulationTraceData(
            alias="current",
            status="passed",
            replaces=SimulationTraceData(alias="older", status="deprecated"),
        ),
    )

    result = invoke("remote", "trace", "abcd1234")

    assert result.exit_code == 0
    assert "current" in result.output
    assert "older" in result.output
    assert trace_simulation.call_args.args == ("abcd1234",)


def test_trace_reports_a_missing_trace(invoke, api_call):
    api_call("trace_simulation", return_value=None)

    result = invoke("remote", "trace", "abcd1234")

    assert result.exit_code == 0
    assert "No simulations trace found" in result.output


# ---------------------------------------------------------------------------
# remote schema
# ---------------------------------------------------------------------------


def test_schema_prints_the_validation_schemas(invoke, api_call):
    api_call("get_validation_schemas", return_value=[{"alias": {"required": True}}])

    result = invoke("remote", "schema")

    assert result.exit_code == 0
    assert "alias" in result.output


def test_schema_rejects_a_non_positive_depth(invoke, api_call):
    get_validation_schemas = api_call("get_validation_schemas", return_value=[])

    result = invoke("remote", "schema", "--depth=0")

    assert result.exit_code == 2
    assert "must be greater than zero" in result.output
    assert not get_validation_schemas.called


# ---------------------------------------------------------------------------
# remote token
# ---------------------------------------------------------------------------


def test_token_new_stores_the_token_in_the_configuration(invoke, api_call, config_file):
    api_call("get_token", return_value="NEWTOKEN")

    result = invoke("remote", "token", "new")

    assert result.exit_code == 0
    assert "Token added for remote test." in result.output
    assert "NEWTOKEN" in config_file.read_text()


def test_token_delete_removes_the_token(invoke, config_file):
    result = invoke("remote", "token", "delete")

    assert result.exit_code == 0
    assert "Token for remote test deleted." in result.output
    assert "123ABC" not in config_file.read_text()


def test_token_delete_can_be_repeated(invoke):
    assert invoke("remote", "token", "delete").exit_code == 0

    result = invoke("remote", "token", "delete")

    assert result.exit_code == 0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Config.delete_option only raises KeyError for a missing section; "
        "configparser.remove_option returns False for a missing option instead "
        "of raising, so the deletion is reported as successful"
    ),
)
def test_token_delete_says_when_there_was_no_token(invoke):
    assert invoke("remote", "token", "delete").exit_code == 0

    result = invoke("remote", "token", "delete")

    assert "No token for remote test found." in result.output


# ---------------------------------------------------------------------------
# remote admin
# ---------------------------------------------------------------------------


def test_admin_set_meta_reports_an_update(invoke, api_call):
    set_metadata = api_call("set_metadata", return_value="old")

    result = invoke("remote", "admin", "set-meta", "abcd1234", "pulse", "134173")

    assert result.exit_code == 0
    assert "old -> 134173" in result.output
    assert set_metadata.call_args.args == ("abcd1234", "pulse", "134173")


def test_admin_set_meta_reports_a_new_value(invoke, api_call):
    api_call("set_metadata", return_value=None)

    result = invoke("remote", "admin", "set-meta", "abcd1234", "pulse", "134173")

    assert result.exit_code == 0
    assert "Added pulse for simulation abcd1234 with value '134173'" in result.output


@pytest.mark.parametrize(
    ("type_name", "value", "expected"),
    [
        ("int", "42", 42),
        ("float", "1.5", 1.5),
        ("string", "42", "42"),
    ],
)
def test_admin_set_meta_converts_the_value(
    invoke, api_call, type_name, value, expected
):
    set_metadata = api_call("set_metadata", return_value=None)

    result = invoke(
        "remote", "admin", "set-meta", "abcd1234", "key", value, f"--type={type_name}"
    )

    assert result.exit_code == 0
    assert set_metadata.call_args.args[2] == expected


def test_admin_set_meta_converts_a_uuid(invoke, api_call):
    set_metadata = api_call("set_metadata", return_value=None)
    value = "12345678123456781234567812345678"

    result = invoke(
        "remote", "admin", "set-meta", "abcd1234", "key", value, "--type=UUID"
    )

    assert result.exit_code == 0
    assert set_metadata.call_args.args[2] == uuid.UUID(value)


def test_admin_set_status_updates_the_status(invoke, api_call):
    update_simulation = api_call("update_simulation", return_value="not validated")

    result = invoke("remote", "admin", "set-status", "abcd1234", "PASSED")

    assert result.exit_code == 0
    assert "not validated -> PASSED" in result.output
    assert update_simulation.call_args.args == (
        "abcd1234",
        Simulation.Status.PASSED,
    )


def test_admin_set_status_rejects_an_unknown_status(invoke, api_call):
    update_simulation = api_call("update_simulation")

    result = invoke("remote", "admin", "set-status", "abcd1234", "excellent")

    assert result.exit_code == 2
    assert not update_simulation.called


def test_admin_del_meta_removes_the_key(invoke, api_call):
    delete_metadata = api_call("delete_metadata")

    result = invoke("remote", "admin", "del-meta", "abcd1234", "pulse")

    assert result.exit_code == 0
    assert "Deleted pulse for simulation abcd1234" in result.output
    assert delete_metadata.call_args.args == ("abcd1234", "pulse")


def test_admin_delete_removes_the_simulation(invoke, api_call):
    delete_simulation = api_call("delete_simulation")

    result = invoke("remote", "admin", "delete", "abcd1234")

    assert result.exit_code == 0
    assert "Deleted simulation abcd1234" in result.output
    assert delete_simulation.call_args.args == ("abcd1234",)
