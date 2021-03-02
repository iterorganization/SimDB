import argparse

from simdb.cli.commands._base import Command
from simdb.config import Config
from simdb.docstrings import inherit_docstrings


@inherit_docstrings
class ModifyCommand(Command):
    """Command to modify a recorded simulations.
    """
    _help = "modify the ingested simulation"

    class ModifyArgs(argparse.Namespace):
        sim_id: str
        alias: str

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")
        parser.add_argument("--alias", help="new alias")

    def run(self, args: ModifyArgs, config: Config) -> None:
        from ...database import get_local_db

        if args.alias is not None:
            db = get_local_db(config)
            simulation = db.get_simulation(args.sim_id)
            simulation.alias = args.alias
            db.session.commit()
        else:
            print("nothing to do")