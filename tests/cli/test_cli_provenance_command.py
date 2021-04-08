from unittest import mock
from click.testing import CliRunner
from simdb.cli.simdb import cli
from utils import config_test_file, get_file_path


@mock.patch('yaml.dump')
def test_provenance_command(dump):
    config_file = config_test_file()
    runner = CliRunner()
    file_name = get_file_path('provenance.yaml')
    result = runner.invoke(cli, [f'--config-file={config_file}', 'provenance', str(file_name)])
    assert result.exception is None
    assert str(file_name) in result.output
    assert dump.called
    (args, kwargs) = dump.call_args
    assert args[1].name == str(file_name)
    assert kwargs == {'default_flow_style': False}
