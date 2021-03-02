from unittest import mock
from simdb.cli.commands.alias import AliasCommand


def test_create_alias_command():
    AliasCommand()


@mock.patch('argparse.ArgumentParser')
def test_alias_command_add_args(parser):
    cmd = AliasCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_alias_run():
    cmd = AliasCommand()
    # ...
