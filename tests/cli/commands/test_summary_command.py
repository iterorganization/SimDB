from unittest import mock
from simdb.cli.commands.summary import SummaryCommand


def test_create_summary_command():
    SummaryCommand()


@mock.patch('argparse.ArgumentParser')
def test_summary_command_add_args(parser):
    cmd = SummaryCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_summary_run():
    cmd = SummaryCommand()
    # ...
