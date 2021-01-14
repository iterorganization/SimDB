from unittest import mock
from simdb.cli.commands import QueryCommand


def test_create_query_command():
    QueryCommand()


@mock.patch('argparse.ArgumentParser')
def test_query_command_add_args(parser):
    cmd = QueryCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_query_run():
    cmd = QueryCommand()
    # ...
