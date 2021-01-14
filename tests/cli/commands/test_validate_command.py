from unittest import mock
from simdb.cli.commands import ValidateCommand


def test_create_validate_command():
    ValidateCommand()


@mock.patch('argparse.ArgumentParser')
def test_validate_command_add_args(parser):
    cmd = ValidateCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_validate_run():
    cmd = ValidateCommand()
    # ...
