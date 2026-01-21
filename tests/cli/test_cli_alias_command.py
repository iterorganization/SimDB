from unittest import mock

from click.testing import CliRunner
from utils import config_test_file

from simdb.cli.simdb import cli

LOCAL_ALIASES = ["hello", "world", "foo-123"]
REMOTE_ALIASES = ["foo#1", "bar", "barfoo", "123foo", "barbaz"]


def _generate_mock_data(get_local_db, remote_list_simulations):
    simulations = []

    for alias in REMOTE_ALIASES:
        sim = mock.Mock()
        sim.alias = alias
        simulations.append(sim)
    remote_list_simulations.return_value = simulations
    simulations = []

    for alias in LOCAL_ALIASES:
        sim = mock.Mock()
        sim.alias = alias
        simulations.append(sim)
    get_local_db().list_simulations.return_value = simulations


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI.list_simulations")
@mock.patch("simdb.cli.remote_api.RemoteAPI.__init__")
def test_alias_search_command(init, remote_list_simulations, get_local_db):
    init.return_value = None
    _generate_mock_data(get_local_db, remote_list_simulations)

    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "alias", "search", "foo"]
    )
    assert result.exception is None
    expected_sims = ["foo#1", "barfoo", "123foo", "foo-123"]
    assert "\n".join(expected_sims) in result.output


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI.list_simulations")
@mock.patch("simdb.cli.remote_api.RemoteAPI.has_url")
@mock.patch("simdb.cli.remote_api.RemoteAPI.__init__")
def test_alias_list_command(init, has_url, remote_list_simulations, get_local_db):
    init.return_value = None
    has_url.return_value = True
    _generate_mock_data(get_local_db, remote_list_simulations)

    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "alias", "list"])
    assert result.exception is None
    assert "\n  ".join(LOCAL_ALIASES) in result.output


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI.list_simulations")
@mock.patch("simdb.cli.remote_api.RemoteAPI.has_url")
@mock.patch("simdb.cli.remote_api.RemoteAPI.__init__")
def test_alias_list_command_with_remote_name(
    init, has_url, remote_list_simulations, get_local_db
):
    init.return_value = None
    has_url.return_value = True
    _generate_mock_data(get_local_db, remote_list_simulations)

    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "alias", "test", "list"]
    )
    assert result.exception is None
    assert "\n  ".join(REMOTE_ALIASES) in result.output
    assert "\n  ".join(LOCAL_ALIASES) in result.output
