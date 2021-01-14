from unittest import mock
from simdb.cli.commands import ProvenanceCommand


def test_create_provenance_command():
    ProvenanceCommand()


@mock.patch('argparse.ArgumentParser')
def test_provenance_command_add_args(parser):
    cmd = ProvenanceCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_provenance_run():
    cmd = ProvenanceCommand()
    # ...
