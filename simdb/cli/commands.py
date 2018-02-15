import os
import argparse
from typing import Any, Optional, List, Dict

from ..database.database import Database
from ..database.models import Simulation
from .manifest import Manifest, InvalidManifest
from .remote_api import RemoteAPI


def get_db() -> Database:
    db_dir = os.path.join(os.environ["HOME"], ".simdb")
    os.makedirs(db_dir, exist_ok=True)
    db_file = os.path.join(db_dir, "sim.db")
    database = Database(Database.Type.SQLITE, file=db_file)
    return database


class Command:
    _help: str = NotImplemented

    @property
    def help(self):
        return type(self)._help

    def add_arguments(self, parser: argparse.ArgumentParser):
        pass

    def run(self, args: Any):
        raise NotImplementedError


class IngestCommand(Command):
    _help = "ingest a manifest file"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("manifest_file", help="manifest file location")
        parser.add_argument("--alias", "-a", help="alias of an existing manifest to update, or a new alias use")
        parser.add_argument("--uuid", "-u", help="uuid of an already ingested manifest to update")
        parser.add_argument("--update", action="store_true", help="update an existing manifest")

    class IngestArgs(argparse.Namespace):
        manifest_file: str
        alias: Optional[str]
        uuid: Optional[str]
        update: bool

    def run(self, args: IngestArgs):
        manifest = Manifest()
        manifest.load(args.manifest_file)
        database = get_db()
        database.ingest(manifest, args.alias)


def list_simulations(simulations: List[Simulation], verbose: bool=False) -> None:
    if len(simulations) == 0:
        print("No simulations found")
        return

    print("UUID%s alias" % (" " * 32), end="")
    max_alias = max(len(str(sim.alias)) for sim in simulations)
    max_alias = max(max_alias, 5)
    if verbose:
        print("%s datetime%s status" % (" " * (max_alias - 5), " " * 18), end="")
    print()
    print("-" * (37 + max_alias + (35 if verbose else 0)))

    for sim in simulations:
        print("%s %s" % (sim.uuid, sim.alias), end="")
        if verbose:
            alias_len = len(str(sim.alias))
            print("%s %s %s" % (" " * (max_alias - alias_len), sim.datetime, sim.status), end="")
        print()


class ListCommand(Command):
    _help = "list ingested manifests"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("--verbose", "-v", action="store_true", help="print more verbose output")

    class ListArgs(argparse.Namespace):
        verbose: bool

    def run(self, args: ListArgs) -> None:
        database = get_db()
        simulations = database.list()
        list_simulations(simulations, verbose=args.verbose)


class DeleteCommand(Command):
    _help = "delete an ingested manifest"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    class DeleteArgs(argparse.Namespace):
        sim_id: str

    def run(self, args: DeleteArgs):
        database = get_db()
        database.delete(args.sim_id)


def print_files(files: List[Dict]):
    for file in files:
        for key, value in file.items():
            key = key.replace("file_", "")
            if key == "id":
                continue
            print("    %s: %s" % (key, value))


class InfoCommand(Command):
    _help = "print information on ingested manifest"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    class InfoArgs(argparse.Namespace):
        sim_id: str

    def run(self, args: InfoArgs):
        database = get_db()
        simulation = database.get(args.sim_id)
        if simulation is None:
            raise Exception("Failed to find simulation: " + args.sim_id)
        print(str(simulation))


class PushCommand(Command):
    _help = "push local manifest to remote system"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    class PushArgs(argparse.Namespace):
        sim_id: str

    def run(self, args: PushArgs):
        api = RemoteAPI()
        database = get_db()
        simulation = database.get(args.sim_id)
        if simulation is None:
            raise Exception("Failed to find simulation: " + args.sim_id)
        print(api.push(simulation))


class RemoteCommand(Command):
    _help = "query remote system"
    _parser: argparse.ArgumentParser

    def add_arguments(self, parser: argparse.ArgumentParser):
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        parser.add_argument("--verbose", "-v", action="store_true", help="print more verbose output")

        commands = {
            "list": ListCommand(),
            "info": InfoCommand(),
        }

        for name, command in commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class RemoteArgs(argparse.Namespace):
        action: str
        verbose: bool
        sim_id: str

    def run(self, args: RemoteArgs):
        if args.action == "list":
            api = RemoteAPI()
            simulations = api.list()
            list_simulations(simulations, verbose=args.verbose)
        elif args.action == "info":
            api = RemoteAPI()
            simulation = api.get(args.sim_id)
            print(str(simulation))


class ManifestCommand(Command):
    _help = "create/check manifest file"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("action", choices=["check", "create"])
        parser.add_argument("manifest_file", help="manifest file location")

    class ManifestArgs(argparse.Namespace):
        action: str
        manifest_file: str

    def run(self, args: ManifestArgs):
        manifest = Manifest()

        if args.action == "check":
            manifest.load(args.manifest_file)
            try:
                manifest.validate()
                print("ok")
            except InvalidManifest as err:
                print(err)
                return
        elif args.action == "create":
            Manifest.from_template().save(args.manifest_file)


class DatabaseCommand(Command):
    _help = "manage local simulation database file"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("clear", help="clear all ingested simulations from the database")

    def run(self, args: argparse.Namespace):
        database = get_db()
        database.reset()
