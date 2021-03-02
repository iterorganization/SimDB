import argparse

from simdb.cli.commands._base import Command
from simdb.config import Config
from simdb.docstrings import inherit_docstrings


@inherit_docstrings
class DeleteCommand(Command):
    """Command to delete simulation record.
    """
    _help = "delete an ingested manifest"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    class DeleteArgs(argparse.Namespace):
        sim_id: str

    def run(self, args: DeleteArgs, config: Config) -> None:
        from ...database import get_local_db

        db = get_local_db(config)
        db.delete_simulation(args.sim_id)

        print("success")