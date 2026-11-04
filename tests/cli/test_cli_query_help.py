from click.testing import CliRunner
from utils import config_test_file

from simdb.cli.simdb import cli


def _query_help(command: str) -> str:
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", command, "query", "--help"]
    )
    assert result.exit_code == 0, result.output
    body = result.output.split("Each constraint", 1)[1].split("Options:", 1)[0]
    return body.replace(f"simdb {command} query", "simdb COMMAND query")


def test_query_help_shared():
    local = _query_help("simulation")
    assert local == _query_help("remote")
    assert "exist:" in local
    assert "agt:" in local
    assert "simdb COMMAND query global_quantities.r0.value=gt:6" in local
