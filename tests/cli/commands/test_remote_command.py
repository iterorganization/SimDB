from unittest import mock
from simdb.cli.commands.remote import RemoteCommand


def test_create_remote_command():
    RemoteCommand()


@mock.patch('argparse.ArgumentParser')
def test_remote_command_add_args(parser):
    cmd = RemoteCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_remote_run():
    cmd = RemoteCommand()
    # ...
