import argparse
from enum import Enum, auto

from simdb.cli.commands._base import Command, _required_argument
from simdb.config import Config
from simdb.docstrings import inherit_docstrings


@inherit_docstrings
class AliasCommand(Command):
    """Command for querying used aliases"""
    _help = "query remote and local aliases"

    class Actions(Enum):
        SEARCH = auto()
        LIST = auto()

        def __str__(self) -> str:
            return self.name.lower()

        @staticmethod
        def from_string(s: str) -> 'AliasCommand.Actions':
            try:
                return AliasCommand.Actions[s.upper()]
            except KeyError:
                raise ValueError()

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--action", type=AliasCommand.Actions.from_string, choices=list(AliasCommand.Actions),
                            help="action to perform", dest="alias_action")
        parser.add_argument("value", help="search value (only for search action)", nargs='?')

    class AliasArgs(argparse.Namespace):
        alias_action: str
        value: str

    @staticmethod
    def _search_aliases(config: Config, value: str):
        from ..remote_api import RemoteAPI
        from ...database import get_local_db

        api = RemoteAPI(config)
        simulations = api.list_simulations()

        db = get_local_db(config)
        simulations += db.list_simulations()

        aliases = [sim.alias for sim in simulations if sim.alias.contains(value)]
        for alias in aliases:
            print(alias)

    @staticmethod
    def _list_aliases(config: Config):
        from ..remote_api import RemoteAPI
        from ...database import get_local_db

        api = RemoteAPI(config)
        if api.has_url():
            remote_simulations = api.list_simulations()
        else:
            remote_simulations = []
            print('The Remote Server has not been specified in the configuration file. Please set remote-url')

        db = get_local_db(config)
        local_simulations = db.list_simulations()

        print("Remote:")
        for sim in remote_simulations:
            print(" ", sim.alias)

        print("Local:")
        for sim in local_simulations:
            print(" ", sim.alias)

    def run(self, args: AliasArgs, config: Config) -> None:
        if args.alias_action == AliasCommand.Actions.SEARCH:
            _required_argument(args, "search", "value")
            AliasCommand._search_aliases(config, args.value)
        elif args.alias_action == AliasCommand.Actions.LIST:
            AliasCommand._list_aliases(config)