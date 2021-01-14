from unittest import mock
from simdb.cli.commands import DatabaseCommand


def test_create_database_command():
    DatabaseCommand()


@mock.patch('argparse.ArgumentParser')
def test_database_command_add_args(parser):
    cmd = DatabaseCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_database_run():
    cmd = DatabaseCommand()
    # ...
