from unittest import mock
from simdb.cli.commands.modify import ModifyCommand


def test_create_modify_command():
    ModifyCommand()


@mock.patch('argparse.ArgumentParser')
def test_modify_command_add_args(parser):
    cmd = ModifyCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_modify_run():
    cmd = ModifyCommand()
    # ...
