from unittest import mock
from click.testing import CliRunner
from simdb.cli.simdb import cli
from utils import config_test_file
from simdb.notifications import Notification


@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_authentication")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_endpoints")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_api_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.list_watchers")
def test_remote_watchers_list_command(
    list_watchers,
    get_server_version,
    get_api_version,
    get_endpoints,
    get_server_authentication,
):
    get_endpoints.return_value = ["v1", "v1.1", "v1.1.1", "v1.2"]
    get_api_version.return_value = "1.2"
    get_server_version.return_value = "0.11"
    get_server_authentication.return_value = "None"
    sim_id = "acbd1234"
    watchers = ["a", "b", "c"]
    list_watchers.return_value = watchers
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "remote", "watcher", "list", sim_id]
    )
    assert result.exception is None
    assert sim_id in result.output
    for watcher in watchers:
        assert watcher in result.output
    assert list_watchers.called
    assert get_api_version.called


@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_authentication")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_endpoints")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_api_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.remove_watcher")
def test_remote_watcher_remove_command(
    remove_watcher,
    get_server_version,
    get_api_version,
    get_endpoints,
    get_server_authentication,
):
    get_endpoints.return_value = ["v1", "v1.1", "v1.1.1", "v1.2"]
    get_api_version.return_value = "1.2"
    get_server_version.return_value = "0.11"
    get_server_authentication.return_value = "None"
    user = "test"
    sim_id = "acbd1234"
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            f"--config-file={config_file}",
            "remote",
            "watcher",
            "remove",
            sim_id,
            f"--user={user}",
        ],
    )
    assert result.exception is None
    assert sim_id in result.output
    assert remove_watcher.called
    (args, kwargs) = remove_watcher.call_args
    assert args == (sim_id, user)
    assert kwargs == {}
    assert get_api_version.called


@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_authentication")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_endpoints")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_api_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.add_watcher")
def test_remote_watcher_add_command(
    add_watcher,
    get_server_version,
    get_api_version,
    get_endpoints,
    get_server_authentication,
):
    get_endpoints.return_value = ["v1", "v1.1", "v1.1.1", "v1.2"]
    get_api_version.return_value = "1.2"
    get_server_version.return_value = "0.11"
    get_server_authentication.return_value = "None"
    user = "test"
    email = "test@iter.org"
    sim_id = "acbd1234"
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            f"--config-file={config_file}",
            "remote",
            "watcher",
            "add",
            sim_id,
            f"--user={user}",
            f"--email={email}",
            "--notification=all",
        ],
    )
    assert result.exception is None
    assert sim_id in result.output
    assert add_watcher.called
    (args, kwargs) = add_watcher.call_args
    assert args == (sim_id, user, email, Notification.ALL)
    assert kwargs == {}
    assert get_api_version.called


@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_authentication")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_endpoints")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_api_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.list_simulations")
def test_remote_list_command(
    list_simulations,
    get_server_version,
    get_api_version,
    get_endpoints,
    get_server_authentication,
):
    get_endpoints.return_value = ["v1", "v1.1", "v1.1.1", "v1.2"]
    get_api_version.return_value = "1.2"
    get_server_version.return_value = "0.11"
    get_server_authentication.return_value = "None"
    data = [
        ("abcd1234", "test"),
        ("abcd5678", "test"),
        ("abcd4321", "test"),
    ]
    sims = []
    for el in data:
        sim = mock.Mock()
        sim.uuid = el[0]
        sim.alias = el[1]
        sims.append(sim)
    list_simulations.return_value = sims
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "remote", "list", "--uuid"]
    )
    assert result.exception is None
    assert list_simulations.called
    for el in data:
        for i in el:
            assert i in result.output
    assert get_api_version.called


@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_authentication")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_endpoints")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_api_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.list_simulations")
def test_remote_list_command_with_verbose(
    list_simulations,
    get_server_version,
    get_api_version,
    get_endpoints,
    get_server_authentication,
):
    get_endpoints.return_value = ["v1", "v1.1", "v1.1.1", "v1.2"]
    get_api_version.return_value = "1.2"
    get_server_version.return_value = "0.11"
    get_server_authentication.return_value = "None"
    data = [
        ("abcd1234", "test", "2000-01-01-01", "Validated"),
        ("abcd5678", "test", "2000-02-02-02", "Validated"),
        ("abcd4321", "test", "2000-03-03-03", "Validated"),
    ]
    sims = []
    for el in data:
        sim = mock.Mock()
        sim.uuid = el[0]
        sim.alias = el[1]
        sim.datetime = el[2]
        sim.status = el[3]
        sims.append(sim)
    list_simulations.return_value = sims
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "--verbose", "remote", "list", "--uuid"]
    )
    assert result.exception is None
    assert list_simulations.called
    for el in data:
        for i in el:
            assert i in result.output
    assert get_api_version.called


@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_authentication")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_endpoints")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_api_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_simulation")
def test_remote_info_command(
    get_simulation,
    get_server_version,
    get_api_version,
    get_endpoints,
    get_server_authentication,
):
    get_endpoints.return_value = ["v1", "v1.1", "v1.1.1", "v1.2"]
    get_api_version.return_value = "1.2"
    get_server_version.return_value = "0.11"
    get_server_authentication.return_value = "None"
    sim_id = "abcd1234"
    sim = ("abcd1234", "test", "2000-01-01-01", "Validated")
    get_simulation.return_value = sim
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "remote", "info", sim_id]
    )
    assert result.exception is None
    assert str(sim) in result.output
    assert get_simulation.called
    (args, kwargs) = get_simulation.call_args
    assert args == (sim_id,)
    assert kwargs == {}
    assert get_api_version.called


@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_authentication")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_endpoints")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_api_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.query_simulations")
def test_remote_query_command(
    query_simulations,
    get_server_version,
    get_api_version,
    get_endpoints,
    get_server_authentication,
):
    get_endpoints.return_value = ["v1", "v1.1", "v1.1.1", "v1.2"]
    get_api_version.return_value = "1.2"
    get_server_version.return_value = "0.11"
    get_server_authentication.return_value = "None"
    data = [
        ("abcd1234", "123"),
    ]
    sims = []
    for el in data:
        sim = mock.Mock()
        sim.uuid = el[0]
        sim.alias = el[1]
        sim.find_meta.return_value = []
        sims.append(sim)
    constraints = ("alias=123", "description=in:test")
    query_simulations.return_value = sims
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "remote", "query", "--uuid", *constraints]
    )
    assert result.exception is None
    for el in data:
        for i in el:
            assert i in result.output
    assert query_simulations.called
    (args, kwargs) = query_simulations.call_args
    assert args == (constraints, (), 100)
    assert kwargs == {}
    assert get_api_version.called


@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_authentication")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_endpoints")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_api_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_version")
@mock.patch("simdb.cli.remote_api.RemoteAPI.query_simulations")
def test_remote_query_command_with_verbose(
    query_simulations,
    get_server_version,
    get_api_version,
    get_endpoints,
    get_server_authentication,
):
    get_endpoints.return_value = ["v1", "v1.1", "v1.1.1", "v1.2"]
    get_api_version.return_value = "1.2"
    get_server_version.return_value = "0.11"
    get_server_authentication.return_value = "None"
    data = [
        ("abcd1234", "123", "2000-01-01-01", "Validated"),
    ]
    sims = []
    for el in data:
        sim = mock.Mock()
        sim.uuid = el[0]
        sim.alias = el[1]
        sim.datetime = el[2]
        sim.status = el[3]
        sim.find_meta.return_value = []
        sims.append(sim)
    constraints = ("alias=123", "description=in:test")
    query_simulations.return_value = sims
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            f"--config-file={config_file}",
            "--verbose",
            "remote",
            "query",
            "--uuid",
            *constraints,
        ],
    )
    assert result.exception is None
    for el in data:
        for i in el:
            assert i in result.output
    assert query_simulations.called
    (args, kwargs) = query_simulations.call_args
    assert args == (constraints, (), 100)
    assert kwargs == {}
    assert get_api_version.called


# @mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_authentication")
# @mock.patch("simdb.cli.remote_api.RemoteAPI.get_endpoints")
# @mock.patch("simdb.cli.remote_api.RemoteAPI.get_api_version")
# @mock.patch("simdb.cli.remote_api.RemoteAPI.get_server_version")
# @mock.patch("simdb.cli.remote_api.RemoteAPI.update_simulation")
# @mock.patch("simdb.cli.remote_api.RemoteAPI.validate_simulation")
# def test_remote_update_command_with_accept(
#     validate_simulation,
#     update_simulation,
#     get_server_version,
#     get_api_version,
#     get_endpoints,
#     get_server_authentication,
# ):
#     from simdb.database.models.simulation import Simulation

#     get_endpoints.return_value = ["v1", "v1.1", "v1.1.1", "v1.2"]
#     get_api_version.return_value = "1.2"
#     get_server_version.return_value = "0.11"
#     get_server_authentication.return_value = "None"
#     sim_id = "abcd1234"
#     config_file = config_test_file()
#     runner = CliRunner()
#     result = runner.invoke(
#         cli, [f"--config-file={config_file}", "remote", "update", sim_id, "accept"]
#     )
#     print(result.output, result.exception)
#     assert result.exception is None
#     assert sim_id in result.output
#     assert validate_simulation.called
#     (args, kwargs) = validate_simulation.call_args
#     assert args == (sim_id,)
#     assert kwargs == {}
#     assert update_simulation.called
#     (args, kwargs) = update_simulation.call_args
#     assert args == (sim_id, Simulation.Status.ACCEPTED)
#     assert kwargs == {}
#     assert get_api_version.called
