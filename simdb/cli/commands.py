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
    database = Database(Database.DBMS.SQLITE, file=db_file)
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
        manifest.validate()
        simulation = Simulation(manifest)
        simulation.alias = args.alias

        database = get_db()
        database.insert_simulation(simulation)


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
        simulations = database.list_simulations()
        list_simulations(simulations, verbose=args.verbose)


class DeleteCommand(Command):
    _help = "delete an ingested manifest"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    class DeleteArgs(argparse.Namespace):
        sim_id: str

    def run(self, args: DeleteArgs):
        database = get_db()
        database.delete_simulation(args.sim_id)


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
        simulation = database.get_simulation(args.sim_id)
        if simulation is None:
            raise Exception("Failed to find simulation: " + args.sim_id)
        print(str(simulation))


class SimulationCommand(Command):
    _help = "manage ingested simulations"

    def add_arguments(self, parser: argparse.ArgumentParser):
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        class PushCommand(Command):
            _help = "push the simulation to the remote management system"

            def add_arguments(self, parser: argparse.ArgumentParser):
                parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

            def run(self, args: Any):
                pass

        class ModifyCommand(Command):
            _help = "modify the ingested simulation"

            def add_arguments(self, parser: argparse.ArgumentParser):
                parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")
                parser.add_argument("--alias", help="new alias")

            def run(self, args: Any):
                pass

        commands = {
            "push": PushCommand(),
            "modify": ModifyCommand(),
        }

        for name, command in commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class SimulationArgs(argparse.Namespace):
        action: str
        sim_id: str
        alias: str

    def run(self, args: SimulationArgs):
        if args.action == "push":
            api = RemoteAPI()
            database = get_db()
            simulation = database.get_simulation(args.sim_id)
            if simulation is None:
                raise Exception("Failed to find simulation: " + args.sim_id)
            api.push_simulation(simulation)
            print("success")
        elif args.action == "modify":
            if args.alias is not None:
                database = get_db()
                simulation = database.get_simulation(args.sim_id)
                simulation.alias = args.alias
                database.session.commit()
            else:
                print("nothing to do")


class RemoteCommand(Command):
    _help = "query remote system"
    _parser: argparse.ArgumentParser

    def add_arguments(self, parser: argparse.ArgumentParser):
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        parser.add_argument("--verbose", "-v", action="store_true", help="print more verbose output")

        class RemoteDatabaseCommand(Command):
            _help = "manage remote simulation database file"

            def add_arguments(self, parser: argparse.ArgumentParser):
                parser.add_argument("remote_command", choices=["clear"],
                                    help="clear all ingested simulations from the database")

            def run(self, args: argparse.Namespace):
                pass

        class RemoteSimulationCommand(Command):
            _help = "publish staged simulation"

            def add_arguments(self, parser: argparse.ArgumentParser):
                parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

            def run(self, args: Any):
                pass

        commands = {
            "list": ListCommand(),
            "info": InfoCommand(),
            "publish": RemoteSimulationCommand(),
            "delete": RemoteSimulationCommand(),
            "database": RemoteDatabaseCommand(),
        }

        for name, command in commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class RemoteArgs(argparse.Namespace):
        action: str
        verbose: bool
        sim_id: str

    def run(self, args: RemoteArgs):
        api = RemoteAPI()
        if args.action == "list":
            simulations = api.list_simulations()
            list_simulations(simulations, verbose=args.verbose)
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
