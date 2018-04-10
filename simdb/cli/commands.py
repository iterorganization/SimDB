import os
import argparse
from typing import Any, Optional, List, Dict

from ..database.models import Simulation
from .manifest import Manifest, InvalidManifest
from .remote_api import RemoteAPI
from ..database.database import get_local_db
from ..provenance import create_provenance_file, read_provenance_file


def required_argument(args: Any, command: str, argument: str):
    if not getattr(args, argument):
        raise argparse.ArgumentError(None, "--{} name must be provided with {} command".format(argument, command))


class Command:
    _help: str = NotImplemented

    @property
    def help(self):
        return type(self)._help

    def add_arguments(self, parser: argparse.ArgumentParser):
        pass

    def run(self, args: Any):
        raise NotImplementedError


class QueryCommand(Command):
    _help = "query the simulations"

    class QueryArgs(argparse.Namespace):
        verbose: bool
        name: str
        equals: Optional[str]
        contains: Optional[str]
        # greater: Optional[int]
        # greater_equals: Optional[int]
        # less: Optional[int]
        # less_equals: Optional[int]

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("--verbose", "-v", action="store_true", help="print more verbose output")
        parser.add_argument("--name", "-n", help="search name", required=True)
        parser.add_argument("--equals", "-e", help="test equality")
        parser.add_argument("--contains", "-c", help="test string contains")
        # parser.add_argument("--greater", "-gt", help="test greater than", type=int)
        # parser.add_argument("--greater-equals", "-ge", help="test greater than or equals", type=int)
        # parser.add_argument("--less", "-lt", help="test less than", type=int)
        # parser.add_argument("--less-equals", "-le", help="test less than or equals", type=int)

    def run(self, args: QueryArgs, query_type="meta"):
        # if not any([args.equals, args.contains, args.greater, args.greater_equals, args.less, args.less_equals]):
        if not any([args.equals, args.contains]):
            raise argparse.ArgumentTypeError("At least one test must be provided")
        db = get_local_db()
        if query_type == "meta":
            simulations = db.query_meta(args.name, equals=args.equals, contains=args.contains)
        elif query_type == "provenance":
            simulations = db.query_provenance(args.name, equals=args.equals, contains=args.contains)
        else:
            raise Exception("Unknown query type " + query_type)
        list_simulations(simulations, verbose=args.verbose)


class ProvenanceCommand(Command):
    _help = "provenance tools"

    class CreateCommand(Command):
        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("file", help="provenance file")

        def run(self, args: Any):
            create_provenance_file(args.file)

    class IngestCommand(Command):
        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")
            parser.add_argument("file", help="provenance file")

        def run(self, args: Any):
            prov = read_provenance_file(args.file)
            db = get_local_db()
            db.insert_provenance(args.sim_id, prov)

    class PrintCommand(Command):
        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

        def run(self, args: Any):
            required_argument(args, "ingest", "sim_id")
            db = get_local_db()
            prov = db.get_provenance(args.sim_id)
            print(str(prov))

    _create_command = CreateCommand()
    _ingest_command = IngestCommand()
    _print_command = PrintCommand()
    _query_command = QueryCommand()

    def add_arguments(self, parser: argparse.ArgumentParser):
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        commands = {
            "create": self._create_command,
            "ingest": self._ingest_command,
            "query": self._query_command,
            "print": self._print_command,
        }

        for name, command in commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class ProvenanceArgs(QueryCommand.QueryArgs):
        action: str
        file: Optional[str]
        sim_id: Optional[str]

    def run(self, args: ProvenanceArgs):
        if args.action == "create":
            self._create_command.run(args)
        elif args.action == "ingest":
            self._ingest_command.run(args)
        elif args.action == "print":
            self._print_command.run(args)
        elif args.action == "query":
            self._query_command.run(args, "provenance")
        else:
            raise Exception("Unknown command " + args.action)


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

        database = get_local_db()
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
        database = get_local_db()
        simulations = database.list_simulations()
        list_simulations(simulations, verbose=args.verbose)


class DeleteCommand(Command):
    _help = "delete an ingested manifest"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    class DeleteArgs(argparse.Namespace):
        sim_id: str

    def run(self, args: DeleteArgs):
        database = get_local_db()
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

    class InfoArgs(argparse.Namespace):
        sim_id: str

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    def run(self, args: InfoArgs):
        database = get_local_db()
        simulation = database.get_simulation(args.sim_id)
        if simulation is None:
            raise Exception("Failed to find simulation: " + args.sim_id)
        print(str(simulation))


class PushCommand(Command):
    _help = "push the simulation to the remote management system"

    class PushArgs(argparse.Namespace):
        sim_id: str

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    def run(self, args: PushArgs):
        api = RemoteAPI()
        database = get_local_db()
        simulation = database.get_simulation(args.sim_id)
        if simulation is None:
            raise Exception("Failed to find simulation: " + args.sim_id)
        api.push_simulation(simulation)
        print("success")


class ModifyCommand(Command):
    _help = "modify the ingested simulation"

    class ModifyArgs(argparse.Namespace):
        sim_id: str
        alias: str

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")
        parser.add_argument("--alias", help="new alias")

    def run(self, args: ModifyArgs):
        if args.alias is not None:
            database = get_local_db()
            simulation = database.get_simulation(args.sim_id)
            simulation.alias = args.alias
            database.session.commit()
        else:
            print("nothing to do")


class SimulationCommand(Command):
    _help = "manage ingested simulations"

    def add_arguments(self, parser: argparse.ArgumentParser):
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        commands = {
            "push": PushCommand(),
            "modify": ModifyCommand(),
            "list": ListCommand(),
            "info": InfoCommand(),
            "delete": DeleteCommand(),
            "query": QueryCommand(),
        }

        for name, command in commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class SimulationArgs(PushCommand.PushArgs, ModifyCommand.ModifyArgs, ListCommand.ListArgs, DeleteCommand.DeleteArgs,
                         InfoCommand.InfoArgs, QueryCommand.QueryArgs):
        action: str

    def run(self, args: SimulationArgs):
        if args.action == "push":
            PushCommand().run(args)
        elif args.action == "modify":
            ModifyCommand().run(args)
        elif args.action == "list":
            ListCommand().run(args)
        elif args.action == "info":
            InfoCommand().run(args)
        elif args.action == "delete":
            DeleteCommand().run(args)
        elif args.action == "query":
            QueryCommand().run(args)


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
        database = get_local_db()
        database.reset()
