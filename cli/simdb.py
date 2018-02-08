import argparse
from typing import List

from .database import Database
from .remote_api import RemoteAPI
from .manifest import Manifest
from .file_system import FileSystem


# Database - for accessing sqlite3 database
# RemoteAPI - for interacting with the remote API
# Manifest - for manipulating the manifest file
# FileSystem - for interacting with the file system


class Command:
    _help = NotImplemented

    @property
    def help(self):
        return self._help

    def add_arguments(self, parser: argparse.ArgumentParser):
        raise NotImplementedError

    def run(self, args: argparse.Namespace):
        raise NotImplementedError


class IngestCommand(Command):
    _help = "ingest a manifest file"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("manifest_file", help="manifest file location")

    def run(self, args: argparse.Namespace):
        raise NotImplementedError


class ListCommand(Command):
    _help = "list ingested manifests"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("id", help="simulation UUID or alias")

    def run(self, args: argparse.Namespace):
        raise NotImplementedError


class DeleteCommand(Command):
    _help = "delete an ingested manifest"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("id", help="simulation UUID or alias")

    def run(self, args: argparse.Namespace):
        raise NotImplementedError


class InfoCommand(Command):
    _help = "print information on ingested manifest"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("id", help="simulation UUID or alias")

    def run(self, args: argparse.Namespace):
        raise NotImplementedError


class PushCommand(Command):
    _help = "push local manifest to remote system"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("id", help="simulation UUID or alias")

    def run(self, args: argparse.Namespace):
        raise NotImplementedError


class ManifestCommand(Command):
    _help = "create/check manifest file"

    def add_arguments(self, parser):
        parser.add_argument("--create", action="store_true", help="create a template manifest file")
        parser.add_argument("--check", action="store_true", help="validate a manifest file")
        parser.add_argument("manifest_file", help="manifest file location")

    def run(self, args: argparse.Namespace):
        raise NotImplementedError


class SimCLI:

    commands = {
        "ingest": IngestCommand(),
        "list": ListCommand(),
        "delete": DeleteCommand(),
        "push": PushCommand(),
        "manifest": ManifestCommand(),
    }

    def run(self, args: List[str]):
        parser = argparse.ArgumentParser()

        command_parsers = parser.add_subparsers(title="commands", dest="command")

        for name, command in self.commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

        parsed_args = parser.parse_args(args)

        if parsed_args.command is None:
            parser.print_usage()
            raise SystemExit()

        self.commands[parsed_args.command].run(parsed_args)


def main(args: List[str]):
    """
    Main CLI entry function

    :param args: command line arguments
    :return:
    """
    cli = SimCLI()
    cli.run(args)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])