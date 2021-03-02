import argparse
from typing import Optional

from ._base import Command
from .modify import ModifyCommand
from .delete import DeleteCommand
from . import InfoCommand, IngestCommand, ListCommand, PushCommand, QueryCommand, ValidateCommand
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class SimulationCommand(Command):
    """Command group for working with simulations including ingesting, querying and listing them.
    """
    _help = "manage ingested simulations"

    class NewCommand(Command):
        _help = "create a new blank simulation and return the UUID"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--alias", "-a", help="alias of to assign to the simulation")
            parser.add_argument("--uuid-only", "-u", dest="uuid", default=False, action="store_true",
                                help="return a new UUID but do not insert the new simulation into the database")

        class NewArgs(argparse.Namespace):
            alias: str

        def run(self, args: NewArgs, config: Config) -> None:
            from ...database import get_local_db
            from ...database.models import Simulation
            from ..manifest import Manifest

            simulation = Simulation(Manifest())
            simulation.alias = args.alias
            if not args.uuid:
                db = get_local_db(config)
                db.insert_simulation(simulation)
            print(simulation.uuid)

    class AliasCommand(Command):
        _help = "generated a new unique alias"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--prefix", "-p", help="prefix to use for the alias")

        class AliasArgs(argparse.Namespace):
            prefix: Optional[str]

        def run(self, args: AliasArgs, config: Config) -> None:
            from ...database import get_local_db

            prefix: str = args.prefix or 'sim'

            db = get_local_db(config)
            aliases = db.get_aliases(prefix)

            n = 1
            alias = prefix + ('%03d' % n)

            print(aliases)

            while alias in aliases:
                n += 1
                alias = prefix + ('%03d' % n)

            print(alias)

    _commands = {
        "push": PushCommand(),
        "modify": ModifyCommand(),
        "list": ListCommand(),
        "info": InfoCommand(),
        "delete": DeleteCommand(),
        "query": QueryCommand(),
        "ingest": IngestCommand(),
        "validate": ValidateCommand(),
        "new": NewCommand(),
        "alias": AliasCommand(),
    }

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        for name, command in self._commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class SimulationArgs(PushCommand.PushArgs, ModifyCommand.ModifyArgs, ListCommand.ListArgs, DeleteCommand.DeleteArgs,
                         InfoCommand.InfoArgs, QueryCommand.QueryArgs):
        action: str

    def run(self, args: SimulationArgs, config: Config) -> None:
        self._commands[args.action].run(args, config)