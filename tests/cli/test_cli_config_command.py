from unittest import mock

from click.testing import CliRunner
from utils import config_test_file

from simdb.cli.simdb import cli


@mock.patch("simdb.config.config.Config.get_option")
def test_config_get(get_option):
    config_file = config_test_file()
    get_option.return_value = "bar"
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "config", "get", "foo"]
    )
    assert result.exception is None
    assert "bar" in result.output
    (args, kwargs) = get_option.call_args
    assert args == ("foo",)
    assert kwargs == {}


@mock.patch("simdb.config.config.Config.save")
@mock.patch("simdb.config.config.Config.set_option")
def test_config_set(set_option, save):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "config", "set", "foo", "bar"]
    )
    assert result.exception is None
    (args, kwargs) = set_option.call_args
    assert args == ("foo", "bar")
    assert kwargs == {}
    assert save.called
