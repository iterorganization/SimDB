from unittest import mock
from click.testing import CliRunner
from simdb.cli.simdb import cli
from config_utils import config_test_file


@mock.patch('simdb.database.get_local_db')
@mock.patch('simdb.cli.remote_api.RemoteAPI')
def test_config_delete(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f'--config-file={config_file}', 'config'])
    assert result.exception is None


@mock.patch('simdb.database.get_local_db')
@mock.patch('simdb.cli.remote_api.RemoteAPI')
def test_config_get(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f'--config-file={config_file}', 'config'])
    assert result.exception is None


@mock.patch('simdb.database.get_local_db')
@mock.patch('simdb.cli.remote_api.RemoteAPI')
def test_config_get(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f'--config-file={config_file}', 'config'])
    assert result.exception is None


@mock.patch('simdb.database.get_local_db')
@mock.patch('simdb.cli.remote_api.RemoteAPI')
def test_config_get(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f'--config-file={config_file}', 'config'])
    assert result.exception is None
