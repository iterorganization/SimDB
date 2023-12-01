from unittest import mock
from click.testing import CliRunner
from simdb.cli.simdb import cli
from utils import config_test_file


@mock.patch("simdb.database.get_local_db")
def test_database_clear_command(get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "database", "clear"])
    assert result.exception is None
    assert get_local_db().reset.called
