from unittest import mock
from simdb.cli.commands import DeleteCommand


def test_create_delete_command():
    DeleteCommand()


@mock.patch('argparse.ArgumentParser')
def test_delete_command_add_args(parser):
    cmd = DeleteCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_delete_run():
    cmd = DeleteCommand()
    # ...
