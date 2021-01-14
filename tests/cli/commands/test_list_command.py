from unittest import mock
from simdb.cli.commands import ListCommand


def test_create_list_command():
    ListCommand()


@mock.patch('argparse.ArgumentParser')
def test_list_command_add_args(parser):
    cmd = ListCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_list_run():
    cmd = ListCommand()
    # ...
