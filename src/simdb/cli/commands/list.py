import argparse

from ._base import Command, _list_simulations
from simdb.config import Config
from simdb.docstrings import inherit_docstrings


@inherit_docstrings
class ListCommand(Command):
    """Command to list all recorded simulations.
    """
    _help = "list ingested manifests"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("--verbose", "-v", action="store_true", help="print more verbose output")

    class ListArgs(argparse.Namespace):
        verbose: bool

    def run(self, args: ListArgs, config: Config) -> None:
        from ...database import get_local_db

        db = get_local_db(config)
        simulations = db.list_simulations()
        _list_simulations(simulations, verbose=args.verbose)