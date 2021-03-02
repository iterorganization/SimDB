from unittest import mock
from simdb.cli.commands.info import InfoCommand


def test_create_info_command():
    InfoCommand()


@mock.patch('argparse.ArgumentParser')
def test_info_command_add_args(parser):
    cmd = InfoCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_info_run():
    cmd = InfoCommand()
    # ...
