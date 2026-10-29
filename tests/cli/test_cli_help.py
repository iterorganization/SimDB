import pytest
from click.testing import CliRunner
from utils import config_test_file

from simdb.cli.simdb import cli


@pytest.mark.parametrize(
    "args, usage",
    [
        ((), "simdb"),
        (("simulation",), "simdb simulation"),
        (("simulation", "list"), "simdb simulation list"),
    ],
)
def test_short_help_option(args, usage):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", *args, "-h"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith(f"Usage: {usage} [OPTIONS]")
