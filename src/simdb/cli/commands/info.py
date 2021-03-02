import argparse

from ._base import Command
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class InfoCommand(Command):
    """Command to print information about recorded simulation.
    """
    _help = "print information on ingested manifest"

    class InfoArgs(argparse.Namespace):
        sim_id: str

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    def run(self, args: InfoArgs, config: Config) -> None:
        from ...database import get_local_db

        db = get_local_db(config)
        simulation = db.get_simulation(args.sim_id)
        if simulation is None:
            raise Exception("Failed to find simulation: " + args.sim_id)
        print(str(simulation))