import argparse
from typing import List

from .database import Database
from .remote_api import RemoteAPI
from .manifest import Manifest
from .file_system import FileSystem
from .config import Configuration
from .commands import IngestCommand, ListCommand, DeleteCommand, PushCommand, ManifestCommand


# Database - for accessing sqlite3 database
# RemoteAPI - for interacting with the remote API
# Manifest - for manipulating the manifest file
# FileSystem - for interacting with the file system
# Configuration - user configuration, i.e. ~/.simdb/config


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
