import argparse
import sys

from ._base import Command
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class PushCommand(Command):
    """Command to push a recorded simulation to the remote simdb server.
    """
    _help = "push the simulation to the remote management system"

    class PushArgs(argparse.Namespace):
        sim_id: str

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    def run(self, args: PushArgs, config: Config) -> None:
        from ...database import get_local_db
        from ..remote_api import RemoteAPI

        api = RemoteAPI(config)
        db = get_local_db(config)
        simulation = db.get_simulation(args.sim_id)
        if simulation is None:
            raise Exception("Failed to find simulation: " + args.sim_id)
        api.push_simulation(simulation, out_stream=sys.stdout)

        print("success")