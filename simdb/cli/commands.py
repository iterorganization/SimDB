import os
import argparse
from typing import (Any, Optional, List, Dict, Tuple, TYPE_CHECKING)
from enum import (Enum, auto)

if TYPE_CHECKING:
    from ..database.models import Simulation, ValidationParameters, Summary


def required_argument(args: Any, command: str, argument: str):
    if not getattr(args, argument):
        raise argparse.ArgumentError(None, "{} name must be provided with {} command".format(argument, command))


def flatten_dict(values: Dict) -> List[Tuple[str, str]]:
    items = []
    for (k, v) in values.items():
        if type(v) == list:
            for n, i in enumerate(v):
                items.append(("{}[{}]".format(k, n), i))
        elif type(v) == dict:
            for i in flatten_dict(v):
                items.append(("{}.{}".format(k, i[0]), i[1]))
        else:
            items.append((k, v))
    return items


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

    class QueryType(Enum):
        META = auto()
        PROVENANCE = auto()
        SUMMARY = auto()

    def __init__(self, query_type: QueryType=QueryType.META) -> None:
        self._query_type = query_type

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("name", help="search name")
        parser.add_argument("-v", "--verbose", action="store_true", help="print more verbose output")
        parser.add_argument("-e", "--equals", help="test equality")
        parser.add_argument("-c", "--contains", help="test string contains")
        # parser.add_argument("--greater", "-gt", help="test greater than", type=int)
        # parser.add_argument("--greater-equals", "-ge", help="test greater than or equals", type=int)
        # parser.add_argument("--less", "-lt", help="test less than", type=int)
        # parser.add_argument("--less-equals", "-le", help="test less than or equals", type=int)

    def run(self, args: QueryArgs):
        # if not any([args.equals, args.contains, args.greater, args.greater_equals, args.less, args.less_equals]):
        if not any([args.equals, args.contains]):
            raise argparse.ArgumentTypeError("At least one test must be provided")

        from ..database.database import get_local_db

        db = get_local_db()
        if self._query_type == QueryCommand.QueryType.META:
            simulations = db.query_meta(args.name, equals=args.equals, contains=args.contains)
        elif self._query_type == QueryCommand.QueryType.PROVENANCE:
            simulations = db.query_provenance(args.name, equals=args.equals, contains=args.contains)
        elif self._query_type == QueryCommand.QueryType.SUMMARY:
            simulations = db.query_summary(args.name, equals=args.equals, contains=args.contains)
        else:
            raise Exception("Unknown query type " + self._query_type.name)
        list_simulations(simulations, verbose=args.verbose)


class ProvenanceCommand(Command):
    _help = "provenance tools"

    class CreateCommand(Command):
        _help = "create the provenance file from the current system"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("file", help="provenance file")

        def run(self, args: Any):
            from ..provenance import create_provenance_file

            create_provenance_file(args.file)

    class IngestCommand(Command):
        _help = "ingest the provenance file"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")
            parser.add_argument("file", help="provenance file")

        def run(self, args: Any):
            from ..database.database import get_local_db
            from ..provenance import read_provenance_file

            prov = read_provenance_file(args.file)
            db = get_local_db()
            db.insert_provenance(args.sim_id, prov)

    class PrintCommand(Command):
        _help = "print the provenance for a simulation"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

        def run(self, args: Any):
            from ..database.database import get_local_db
            required_argument(args, "ingest", "sim_id")
            db = get_local_db()
            prov = db.get_provenance(args.sim_id)
            print(str(prov))

    _commands = {
        "create": CreateCommand(),
        "ingest": IngestCommand(),
        "print": PrintCommand(),
        "query": QueryCommand(QueryCommand.QueryType.PROVENANCE),
    }

    def add_arguments(self, parser: argparse.ArgumentParser):
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        for name, command in self._commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class ProvenanceArgs(QueryCommand.QueryArgs):
        action: str
        file: Optional[str]
        sim_id: Optional[str]

    def run(self, args: ProvenanceArgs):
        self._commands[args.action].run(args)


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
        from ..database.database import get_local_db
        from ..database.models import Simulation
        from .manifest import Manifest

        manifest = Manifest()
        manifest.load(args.manifest_file)
        manifest.validate()
        # verify_metadata({}, manifest.metadata)

        simulation = Simulation(manifest)
        simulation.alias = args.alias

        db = get_local_db()
        db.insert_simulation(simulation)


def list_simulations(simulations: List["Simulation"], verbose: bool=False) -> None:
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


def list_validation_parameters(parameters: List["ValidationParameters"]) -> None:
    if len(parameters) == 0:
        print("No validation parameters found")
        return

    max_device = max(len(str(param.device)) for param in parameters)
    max_device = max(max_device, 6)
    device_spaces = (6 - max_device)
    print("Device%s Scenario" % (" " * device_spaces))
    print("-" * (15 + device_spaces))

    for param in parameters:
        print("%s%s %s" % (param.device, " " * (max_device - len(param.device)), param.scenario))


def list_summaries(summaries: List["Summary"]) -> None:
    if len(summaries) == 0:
        print("No summaries found")
        return

    for summary in summaries:
        print("{} = {}".format(summary.key, summary.value))


class ListCommand(Command):
    _help = "list ingested manifests"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("--verbose", "-v", action="store_true", help="print more verbose output")

    class ListArgs(argparse.Namespace):
        verbose: bool

    def run(self, args: ListArgs) -> None:
        from ..database.database import get_local_db

        db = get_local_db()
        simulations = db.list_simulations()
        list_simulations(simulations, verbose=args.verbose)


class DeleteCommand(Command):
    _help = "delete an ingested manifest"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    class DeleteArgs(argparse.Namespace):
        sim_id: str

    def run(self, args: DeleteArgs):
        from ..database.database import get_local_db

        db = get_local_db()
        db.delete_simulation(args.sim_id)


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
        from ..database.database import get_local_db

        db = get_local_db()
        simulation = db.get_simulation(args.sim_id)
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
        from ..database.database import get_local_db
        from .remote_api import RemoteAPI

        api = RemoteAPI()
        db = get_local_db()
        simulation = db.get_simulation(args.sim_id)
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
        from ..database.database import get_local_db

        if args.alias is not None:
            db = get_local_db()
            simulation = db.get_simulation(args.sim_id)
            simulation.alias = args.alias
            db.session.commit()
        else:
            print("nothing to do")


class ValidateCommand(Command):
    _help = "validate the ingested simulation"

    class ValidateArgs(argparse.Namespace):
        sim_id: str

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    def run(self, args: ValidateArgs):
        from itertools import chain
        from ..database.database import get_local_db
        from ..validation import ValidationError
        from ..imas import validation as imas_validation
        from .manifest import DataObject

        db = get_local_db()
        simulation = db.get_simulation(args.sim_id)
        device = simulation.find_meta("device")
        scenario = simulation.find_meta("scenario")
        if not device:
            raise ValidationError("No device found in metadata")
        if len(device) > 1:
            raise ValidationError("Multiple devices found in metadata")
        if not scenario:
            raise ValidationError("No scenario found in metadata")
        if len(device) > 1:
            raise ValidationError("Multiple scenarios found in metadata")
        imas_names = set()
        for file in chain(simulation.inputs, simulation.outputs):
            if file.type == DataObject.Type.UDA:
                from ..uda.checksum import checksum as uda_checksum
                checksum = uda_checksum(file.file_name, file.directory)
            else:
                from ..checksum import sha1_checksum
                path = os.path.join(file.directory, file.file_name)
                checksum = sha1_checksum(path)
            if checksum != file.checksum:
                raise ValidationError("Checksum doest not match for file " + path)
            if file.type == DataObject.Type.IMAS:
                imas_names.add(file.file_name.split(".")[0])
        for name in imas_names:
            (tree, num) = name.split("_")
            shot = int(num[:-4])
            run = int(num[-4:])
            imas_obj = imas_validation.load_imas(shot, run)
            imas_validation.validate_imas(device[0].value, scenario[0].value, imas_obj)


class SimulationCommand(Command):
    _help = "manage ingested simulations"

    class NewCommand(Command):
        _help = "create a new blank simulation and return the UUID"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("--alias", "-a", help="alias of to assign to the simulation")

        class NewArgs(argparse.Namespace):
            alias: str

        def run(self, args: NewArgs) -> None:
            from ..database.database import get_local_db
            from ..database.models import Simulation
            from .manifest import Manifest

            db = get_local_db()
            simulation = Simulation(Manifest())
            simulation.alias = args.alias
            db.insert_simulation(simulation)
            print(simulation.uuid)

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
    }

    def add_arguments(self, parser: argparse.ArgumentParser):
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        for name, command in self._commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class SimulationArgs(PushCommand.PushArgs, ModifyCommand.ModifyArgs, ListCommand.ListArgs, DeleteCommand.DeleteArgs,
                         InfoCommand.InfoArgs, QueryCommand.QueryArgs):
        action: str

    def run(self, args: SimulationArgs):
        self._commands[args.action].run(args)


class SummaryCommand(Command):
    _help = "create and ingest IMAS summaries"

    class SummaryCreateCommand(Command):
        _help = "create the summary file"
        _script = "/work/imas/extra/bin/create_db_entry"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("file", help="file to create")
            parser.add_argument("shot", help="IDS shot")
            parser.add_argument("run", help="IDS run")

        def run(self, args: Any):
            cmd = "{} --shot={} --run={}".format(self._script, args.shot, args.run)
            with os.popen(cmd) as p:
                with open(args.file) as f:
                    for line in p:
                        print(line, file=f, end="")

    class SummaryIngestCommand(Command):
        _help = "ingest the summary file"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")
            parser.add_argument("file", help="file to create")

        def run(self, args: Any):
            from ..database.database import get_local_db
            import yaml

            with open(args.file) as f:
                y = yaml.load(f)
                summary = flatten_dict(y)
            db = get_local_db()
            db.insert_summary(args.sim_id, summary)

    class SummaryListCommand(Command):
        _help = "list the ingested summaries"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

        class SummaryListArgs(argparse.Namespace):
            sim_id: str

        def run(self, args: SummaryListArgs) -> None:
            from ..database.database import get_local_db

            db = get_local_db()
            summaries = db.list_summaries(args.sim_id)
            list_summaries(summaries)

    _commands = {
        "create": SummaryCreateCommand(),
        "ingest": SummaryIngestCommand(),
        "query": QueryCommand(QueryCommand.QueryType.SUMMARY),
        "list": SummaryListCommand(),
    }

    def add_arguments(self, parser: argparse.ArgumentParser):
        command_parsers = parser.add_subparsers(title="action", dest="sum_action")
        command_parsers.required = True

        for name, command in self._commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class SummaryArgs():
        sum_action: str

    def run(self, args: SummaryArgs):
        self._commands[args.sum_action].run(args)


class RemoteDatabaseCommand(Command):
    _help = "manage remote simulation database file"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("remote_command", choices=["clear"],
                            help="clear all ingested simulations from the db")

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

        parser.add_argument("-v", "--verbose", action="store_true", help="print more verbose output")

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
        from .remote_api import RemoteAPI

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
        from .manifest import (Manifest, InvalidManifest)

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

    class ClearCommand(Command):
        _help = "clear the database"

        def add_arguments(self, parser: argparse.ArgumentParser):
            pass

        def run(self, args: Any):
            from ..database.database import get_local_db

            db = get_local_db()
            db.reset()

    class ControlledVocabularyCommand(Command):
        _help = "manage controlled vocabulary"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("cv_action", choices=["new", "update", "clear", "list", "print", "delete"],
                                help="action to perform")
            parser.add_argument("name", help="vocabulary name", nargs="?")
            parser.add_argument("words", nargs="*", help="vocabulary words")

        def run(self, args: Any):
            from ..database.database import get_local_db

            db = get_local_db()
            if args.cv_action == "new":
                required_argument(args, "new", "name")
                required_argument(args, "new", "words")
                db.new_vocabulary(args.name, args.words)
            elif args.cv_action == "update":
                required_argument(args, "update", "name")
                required_argument(args, "update", "words")
                db.clear_vocabulary_words(args.name, args.words)
            elif args.cv_action == "clear":
                required_argument(args, "clear", "name")
                db.clear_vocabulary(args.name)
            elif args.cv_action == "delete":
                required_argument(args, "delete", "name")
                db.delete_vocabulary(args.name)
            elif args.cv_action == "list":
                vocabs = db.get_vocabularies()
                for vocab in vocabs:
                    print("{} - {} words".format(vocab.name, len(vocab.words)))
            elif args.cv_action == "print":
                required_argument(args, "print", "name")
                vocab = db.get_vocabulary(args.name)
                print(vocab.name + ':')
                for word in vocab.words:
                    print('  ' + word.value)
            else:
                raise Exception("Unknown action " + args.cv_action)

    class ReferenceCommand(Command):
        _help = "manage reference scenarios"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("ref_action", choices=["load", "list", "print", "delete"],
                                help="action to perform")
            parser.add_argument("--shot", help="IDS shot number", type=int)
            parser.add_argument("--run", help="IDS run number", type=int)
            parser.add_argument("--device", help="device name")
            parser.add_argument("--scenario", help="scenario name")
            parser.add_argument("--path", help="ids path")
            parser.add_argument("--ids", help="names of the IDSs to use", action="append")

        def run(self, args: Any):
            from ..database.database import get_local_db
            from ..imas import validation as imas_validation
            from ..validation import TestParameters

            db = get_local_db()
            if args.ref_action == "load":
                required_argument(args, "load", "shot")
                required_argument(args, "load", "run")
                required_argument(args, "load", "device")
                required_argument(args, "load", "scenario")
                required_argument(args, "load", "ids")
                imas_obj = imas_validation.load_imas(args.shot, args.run)
                imas_validation.save_validation_parameters(args.device, args.scenario, imas_obj, args.ids)
            elif args.ref_action == "delete":
                pass
            elif args.ref_action == "list":
                params = db.list_validation_parameters(None, None)
                list_validation_parameters(params)
            elif args.ref_action == "print":
                required_argument(args, "print", "device")
                required_argument(args, "print", "scenario")
                params = db.list_validation_parameters(args.device, args.scenario)
                print("Device: {}\nScenario: {}\nPaths:".format(args.device, args.scenario))
                for param in params:
                    print("{} {}".format(param.path, str(TestParameters.from_db_parameters(param))))
            else:
                raise Exception("Unknown action " + args.cv_action)

    _commands = {
        "clear": ClearCommand(),
        "cv": ControlledVocabularyCommand(),
        "reference": ReferenceCommand(),
    }

    def add_arguments(self, parser: argparse.ArgumentParser):
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        for name, command in self._commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    def run(self, args: argparse.Namespace):
        self._commands[args.action].run(args)
