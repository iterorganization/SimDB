from unittest import mock
from simdb.cli.commands import SimulationCommand


def test_create_simulation_command():
    SimulationCommand()


@mock.patch('argparse.ArgumentParser')
def test_simulation_command_add_args(parser):
    cmd = SimulationCommand()
    cmd.add_arguments(parser)
    # parser.add_argument.assert_any_call(...)


def test_simulation_run():
    cmd = SimulationCommand()
    # ...
