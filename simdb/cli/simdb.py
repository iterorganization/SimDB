import argparse
import argcomplete
from typing import List

from .commands import IngestCommand, SimulationCommand, ManifestCommand, DatabaseCommand, RemoteCommand,\
    ProvenanceCommand


class SimCLI:
    """
    Class to provide the simulation management tool command line interface.
    """

    commands = {
        "simulation": SimulationCommand(),
        "manifest": ManifestCommand(),
        "database": DatabaseCommand(),
        "remote": RemoteCommand(),
        "provenance": ProvenanceCommand(),
    }

    def run(self, args: List[str]) -> None:
        """
        Parse the command line arguments and run the command specified.

        :param args: The command line arguments
        :return: None
        """
        parser = argparse.ArgumentParser(prog="simdb")
        parser.add_argument("--debug", "-d", action="store_true", help="run in debug mode")

        command_parsers = parser.add_subparsers(title="commands", dest="command")
        command_parsers.required = True

        for name, command in self.commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

        argcomplete.autocomplete(parser)
        parsed_args = parser.parse_args(args)

        try:
            self.commands[parsed_args.command].run(parsed_args)
        except Exception as ex:
            if parsed_args.debug:
                raise ex
            else:
                print("error: " + (str(ex) if str(ex) else type(ex).__name__))


def main(args: List[str]) -> None:
    """
    Main CLI entry function

    :param args: command line arguments
    :return: None
    """
    cli = SimCLI()
    cli.run(args)
