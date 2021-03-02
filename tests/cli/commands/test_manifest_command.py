from unittest import mock
from simdb.cli.commands.manifest import ManifestCommand


def test_create_manifest_command():
    ManifestCommand()


@mock.patch('argparse.ArgumentParser')
def test_manifest_command_add_args(parser):
    cmd = ManifestCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_manifest_run():
    cmd = ManifestCommand()
    # ...
