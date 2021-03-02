from unittest import mock
from simdb.cli.commands.push import PushCommand


def test_create_push_command():
    PushCommand()


@mock.patch('argparse.ArgumentParser')
def test_push_command_add_args(parser):
    cmd = PushCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_push_run():
    cmd = PushCommand()
    # ...
