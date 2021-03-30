from unittest import mock
from click.testing import CliRunner
from simdb.cli.simdb import cli
from utils import config_test_file

LOCAL_ALIASES = ['hello', 'world', 'foo-123']
REMOTE_ALIASES = ['foo#1', 'bar', 'barfoo', '123foo', 'barbaz']


def _generate_mock_data(get_local_db, remote_api):
    simulations = []

    for alias in REMOTE_ALIASES:
        sim = mock.Mock()
        sim.alias = alias
        simulations.append(sim)
    remote_api().list_simulations.return_value = simulations
    simulations = []

    for alias in LOCAL_ALIASES:
        sim = mock.Mock()
        sim.alias = alias
        simulations.append(sim)
    get_local_db().list_simulations.return_value = simulations


@mock.patch('simdb.database.get_local_db')
@mock.patch('simdb.cli.remote_api.RemoteAPI')
def test_alias_search_command(remote_api, get_local_db):
    _generate_mock_data(get_local_db, remote_api)

    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f'--config-file={config_file}', 'alias', 'search', 'foo'])
    assert result.exception is None
    expected_sims = ['foo#1', 'barfoo', '123foo', 'foo-123']
    assert '\n'.join(expected_sims) in result.output


@mock.patch('simdb.database.get_local_db')
@mock.patch('simdb.cli.remote_api.RemoteAPI')
def test_alias_list_command(remote_api, get_local_db):
    _generate_mock_data(get_local_db, remote_api)

    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f'--config-file={config_file}', 'alias', 'list'])
    assert result.exception is None
    assert '\n  '.join(LOCAL_ALIASES) in result.output


@mock.patch('simdb.database.get_local_db')
@mock.patch('simdb.cli.remote_api.RemoteAPI')
def test_alias_list_command_with_remote_name(remote_api, get_local_db):
    _generate_mock_data(get_local_db, remote_api)

    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f'--config-file={config_file}', 'alias', 'list', 'test'])
    assert result.exception is None
    assert '\n  '.join(REMOTE_ALIASES) in result.output
    assert '\n  '.join(LOCAL_ALIASES) in result.output
