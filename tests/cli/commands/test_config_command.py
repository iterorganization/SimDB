from unittest import mock
from simdb.cli.commands import ConfigCommand


def test_create_config_command():
    ConfigCommand()


@mock.patch('argparse.ArgumentParser')
def test_config_command_add_args(parser):
    cmd = ConfigCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_config_run():
    cmd = ConfigCommand()
    # ...
