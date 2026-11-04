from unittest import mock

from click.testing import CliRunner
from utils import config_test_file, create_manifest, get_file_path

from simdb.cli.simdb import cli


@mock.patch("simdb.cli.commands.manifest.Manifest")
def test_manifest_check_command(manifest):
    config_file = config_test_file()
    runner = CliRunner()
    file_name = create_manifest()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "manifest", "check", str(file_name)]
    )
    assert result.exception is None
    assert "ok" in result.output
    assert manifest.load_from_file.called
    (args, kwargs) = manifest.load_from_file.call_args
    assert str(args[0]) == str(file_name)
    assert kwargs == {}


def test_manifest_check_command_integration():
    """Integration test that actually runs the manifest check without mocking."""
    config_file = config_test_file()
    runner = CliRunner()
    file_name = create_manifest()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "manifest", "check", str(file_name)]
    )
    assert result.exception is None, f"Unexpected exception: {result.exception}"
    assert result.exit_code == 0, (
        f"Exit code: {result.exit_code}, Output: {result.output}"
    )
    assert "ok" in result.output


@mock.patch("simdb.cli.commands.manifest.Manifest")
def test_manifest_create_command(manifest):
    config_file = config_test_file()
    runner = CliRunner()
    file_name = get_file_path("manifest.yaml")
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "manifest", "create", str(file_name)]
    )
    assert result.exception is None
    assert str(file_name) in result.output
    assert manifest.from_template.called
    assert manifest.from_template().save.called
    (args, kwargs) = manifest.from_template().save.call_args
    assert args[0].name == str(file_name)
    assert kwargs == {}


def test_manifest_check_command_reports_error_location(tmp_path):
    config_file = config_test_file()
    runner = CliRunner()
    file_name = tmp_path / "manifest.yaml"
    file_name.write_text("manifest_version: 2\ninputs: []\n outputs: []\n")
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "manifest", "check", str(file_name)]
    )
    assert result.exit_code != 0
    assert "ok" not in result.output
    assert f"{file_name}:3:2: expected <block end>" in str(result.exception)
