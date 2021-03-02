import argparse
from typing import Any

from ._base import Command, _required_argument, _list_validation_parameters
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class DatabaseCommand(Command):
    """Command for manipulating user's local database.
    """
    _help = "manage local simulation database file"

    class ClearCommand(Command):
        _help = "clear the database"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            pass

        def run(self, args: Any, config: Config) -> None:
            from ...database import get_local_db

            db = get_local_db(config)
            db.reset()

    class ControlledVocabularyCommand(Command):
        _help = "manage controlled vocabulary"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("cv_action", choices=["new", "update", "clear", "list", "print", "delete"],
                                help="action to perform")
            parser.add_argument("name", help="vocabulary name", nargs="?")
            parser.add_argument("words", nargs="*", help="vocabulary words")

        def run(self, args: Any, config: Config) -> None:
            from ...database import get_local_db

            db = get_local_db(config)
            if args.cv_action == "new":
                _required_argument(args, "new", "name")
                _required_argument(args, "new", "words")
                db.new_vocabulary(args.name, args.words)
            elif args.cv_action == "update":
                _required_argument(args, "update", "name")
                _required_argument(args, "update", "words")
                db.clear_vocabulary_words(args.name, args.words)
            elif args.cv_action == "clear":
                _required_argument(args, "clear", "name")
                db.clear_vocabulary(args.name)
            elif args.cv_action == "delete":
                _required_argument(args, "delete", "name")
                db.delete_vocabulary(args.name)
            elif args.cv_action == "list":
                vocabs = db.get_vocabularies()
                for vocab in vocabs:
                    print("{} - {} words".format(vocab.name, len(vocab.words)))
            elif args.cv_action == "print":
                _required_argument(args, "print", "name")
                vocab = db.get_vocabulary(args.name)
                print(vocab.name + ':')
                for word in vocab.words:
                    print('  ' + word.value)
            else:
                raise Exception("Unknown action " + args.cv_action)

    class ReferenceCommand(Command):
        _help = "manage reference scenarios"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("ref_action", choices=["load", "list", "print", "delete"],
                                help="action to perform")
            parser.add_argument("--shot", help="IDS shot number", type=int)
            parser.add_argument("--run", help="IDS run number", type=int)
            parser.add_argument("--device", help="device name")
            parser.add_argument("--scenario", help="scenario name")
            parser.add_argument("--path", help="ids path")
            parser.add_argument("--ids", help="names of the IDSs to use", action="append")

        def run(self, args: Any, config: Config) -> None:
            from ...database import get_local_db
            from ...imas import validation as imas_validation
            from ...validation import TestParameters

            db = get_local_db(config)
            if args.ref_action == "load":
                _required_argument(args, "load", "shot")
                _required_argument(args, "load", "run")
                _required_argument(args, "load", "device")
                _required_argument(args, "load", "scenario")
                _required_argument(args, "load", "ids")
                imas_obj = imas_validation.load_imas(args.shot, args.run)
                imas_validation.save_validation_parameters(args.device, args.scenario, imas_obj, args.ids)
            elif args.ref_action == "delete":
                pass
            elif args.ref_action == "list":
                params = db.list_validation_parameters(None, None)
                _list_validation_parameters(params)
            elif args.ref_action == "print":
                _required_argument(args, "print", "device")
                _required_argument(args, "print", "scenario")
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

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        for name, command in self._commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    def run(self, args: argparse.Namespace, config: Config) -> None:
        self._commands[args.action].run(args, config)