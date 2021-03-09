import argparse
import os
from typing import Dict, Any

from email_validator import validate_email, EmailNotValidError

from ._base import Command, _list_simulations
from . import InfoCommand, ListCommand, QueryCommand
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class RemoteCommand(Command):
    """Command for interacting with the remote simdb service.
    """
    _help = "query remote system"
    _parser: argparse.ArgumentParser
    _commands: Dict[str, Command]
    _parsers: Dict[str, argparse.ArgumentParser] = {}

    @inherit_docstrings
    class RemoteDatabaseCommand(Command):
        """Command to manage the remote database [for development use only -- to be removed]."""
        _help = "manage remote simulation database file"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("remote_command", choices=["clear"],
                                help="clear all ingested simulations from the db")

        def run(self, args: argparse.Namespace, _: Config) -> None:
            pass

    @inherit_docstrings
    class RemoteSimulationCommand(Command):
        """Placeholder command to set up arguments for remote manipulations of simulations."""
        def __init__(self, help: str) -> None:
            self._help = help

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

        def run(self, args: Any, _: Config) -> None:
            pass

    @inherit_docstrings
    class WatchCommand(Command):
        """Command to manage the remote database [for development use only -- to be removed]."""
        _help = "manage remote simulation database file"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--user", "-u", help="username of the the user to add as a watcher",
                                default=os.getlogin())
            parser.add_argument("--email", "-e", help="email address of the user to add as a watcher")
            parser.add_argument("--notification", "-n", choices=('validation', 'revision', 'obsolescence', 'all'),
                                help="what event(s) to be notified of for the simulation", default='obsolescence')
            parser.add_argument("--remove", "-r", action="store_true", help="remove the watcher from the simulation")
            parser.add_argument("--list", "-l", action="store_true", help="list existing watchers for the simulation")
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

        def validate_arguments(self, parser: argparse.ArgumentParser, args: Any) -> None:
            if not args.action == 'watch':
                return
            if not (args.remove or args.list):
                if "email" not in args or not args.email:
                    parser.error("email must be provided to add a watcher")
            if "email" in args and args.email:
                try:
                    validate_email(args.email)
                except EmailNotValidError:
                    parser.error("invalid email")

        def run(self, args: argparse.Namespace, config: Config) -> None:
            from ..remote_api import RemoteAPI
            api = RemoteAPI(config)
            if args.list:
                watchers = api.list_watchers(args.sim_id)
                if watchers:
                    print("Watchers for simulation %s:" % args.sim_id)
                    for watcher in api.list_watchers(args.sim_id):
                        print(watcher)
                else:
                    print("no watchers found for simulation " + args.sim_id)
            elif args.remove:
                api.remove_watcher(args.sim_id, args.user)
                print("Watcher successfully removed for simulation " + args.sim_id)
            else:
                api.add_watcher(args.sim_id, args.user, args.email, args.notification)
                print("Watcher successfully added for simulation " + args.sim_id)

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        parser.add_argument("-v", "--verbose", action="store_true", help="print more verbose output")

        self._commands = {
            "list": ListCommand(),
            "info": InfoCommand(),
            "query": QueryCommand(),
            "watch": RemoteCommand.WatchCommand(),
            "publish": RemoteCommand.RemoteSimulationCommand("publish staged simulation"),
            "delete": RemoteCommand.RemoteSimulationCommand("delete staged simulation"),
            "database": RemoteCommand.RemoteDatabaseCommand(),
        }

        for name, command in self._commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            self._parsers[name] = sub_parser
            command.add_arguments(sub_parser)

    def validate_arguments(self, parser: argparse.ArgumentParser, args: Any) -> None:
        for name, command in self._commands.items():
            command.validate_arguments(self._parsers[name], args)

    class RemoteArgs(argparse.Namespace):
        action: str
        verbose: bool
        sim_id: str

    def run(self, args: RemoteArgs, config: Config) -> None:
        from ..remote_api import RemoteAPI

        api = RemoteAPI(config)
        if args.action == "list":
            simulations = api.list_simulations()
            _list_simulations(simulations, verbose=args.verbose)
        elif args.action == "info":
            simulation = api.get_simulation(args.sim_id)
            print(str(simulation))
        elif args.action == "database":
            api.reset_database()
            print("success")
        elif args.action == "publish":
            api.publish_simulation(args.sim_id)
            print("success")
        elif args.action == "delete":
            result = api.delete_simulation(args.sim_id)
            print("deleted simulation: " + result["deleted"]["simulation"])
            if result["deleted"]["files"]:
                for file in result["deleted"]["files"]:
                    print("              file: " + file)
        elif args.action == "query":
            simulations = api.query_simulations(args.constraint)
            _list_simulations(simulations, verbose=args.verbose, metadata_names=args.attributes)
        elif args.action == "watch":
            self._commands["watch"].run(args, config)