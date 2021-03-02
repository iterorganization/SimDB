import argparse
from enum import Enum, auto
from typing import List

from ._base import Command, _list_simulations
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class QueryCommand(Command):
    """Command to perform queries on the Simulation metadata and return the matching simulations.
    """
    _help = "query the simulations"

    class QueryArgs(argparse.Namespace):
        verbose: bool
        constraint: List[str]
        attributes: str

    class QueryType(Enum):
        META = auto()
        PROVENANCE = auto()
        SUMMARY = auto()

    def __init__(self, query_type: QueryType=QueryType.META) -> None:
        """Specify what type of query should be performed by this command, based on the enum value provided.

        :param query_type: the query type to perform when the command is run
        """
        self._query_type = query_type

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("-v", "--verbose", action="store_true", help="print more verbose output")
        parser.add_argument("-a", "--attributes", dest="attributes", default=None,
                            help="list of attributes to include in output")
        parser.add_argument('constraint', nargs='*', help="constraint in the form key=value or key=in:value")

    def run(self, args: QueryArgs, config: Config) -> None:
        if not args.constraint:
            raise argparse.ArgumentTypeError("At least one constraint must be provided")

        from ...database import get_local_db

        equals = {}
        contains = {}
        for item in args.constraint:
            if '=' not in item:
                raise argparse.ArgumentTypeError("Invalid constraint")
            (key, value) = item.split('=')
            if '=in:' in item:
                contains[key] = value.replace('in:', '')
            else:
                equals[key] = value

        db = get_local_db(config)
        if self._query_type == QueryCommand.QueryType.META:
            simulations = db.query_meta(equals=equals, contains=contains)
        elif self._query_type == QueryCommand.QueryType.PROVENANCE:
            simulations = db.query_provenance(equals=equals, contains=contains)
        elif self._query_type == QueryCommand.QueryType.SUMMARY:
            simulations = db.query_summary(equals=equals, contains=contains)
        else:
            raise Exception("Unknown query type " + self._query_type.name)
        _list_simulations(simulations, verbose=args.verbose)