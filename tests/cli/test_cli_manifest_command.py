from unittest import mock
from click.testing import CliRunner
from simdb.cli.simdb import cli
from utils import config_test_file, create_manifest, get_file_path


@mock.patch('simdb.cli.manifest.Manifest')
def test_manifest_check_command(manifest):
    config_file = config_test_file()
    runner = CliRunner()
    file_name = create_manifest()
    result = runner.invoke(cli, [f'--config-file={config_file}', 'manifest', 'check', str(file_name)])
    assert result.exception is None
    assert "ok" in result.output
    assert manifest().load.called
    (args, kwargs) = manifest().load.call_args
    assert args == (str(file_name),)
    assert kwargs == {}
    assert manifest().validate.called


@mock.patch('simdb.cli.manifest.Manifest')
def test_manifest_create_command(manifest):
    config_file = config_test_file()
    runner = CliRunner()
    file_name = get_file_path('manifest.yaml')
    result = runner.invoke(cli, [f'--config-file={config_file}', 'manifest', 'create', str(file_name)])
    assert result.exception is None
    assert str(file_name) in result.output
    assert manifest.from_template.called
    assert manifest.from_template().save.called
    (args, kwargs) = manifest.from_template().save.call_args
    assert args[0].name == str(file_name)
    assert kwargs == {}
