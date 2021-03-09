import argparse
from enum import Enum, auto

from ._base import Command, _required_argument
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class ConfigCommand(Command):
    """Command for querying/editing the user's application configuration"""
    _help = "query/update application configuration"

    class Actions(Enum):
        GET = auto()
        SET = auto()
        LIST = auto()

        def __str__(self) -> str:
            return self.name.lower()

        @staticmethod
        def from_string(s: str) -> 'ConfigCommand.Actions':
            try:
                return ConfigCommand.Actions[s.upper()]
            except KeyError:
                raise ValueError()

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", type=ConfigCommand.Actions.from_string, choices=list(ConfigCommand.Actions),
                            help="action to perform")
        parser.add_argument("option", help="configuration option", nargs='?')
        parser.add_argument("value", help="value to set the option to (only for set action)", nargs='?')

    class ConfigArgs(argparse.Namespace):
        action: str
        option: str
        value: str

    def run(self, args: ConfigArgs, config: Config) -> None:
        if args.action == ConfigCommand.Actions.GET:
            _required_argument(args, "get", "option")
            print(config.get_option(args.option))
        elif args.action == ConfigCommand.Actions.SET:
            _required_argument(args, "set", "option")
            _required_argument(args, "set", "value")
            config.set_option(args.option, args.value)
            config.save()
        elif args.action == ConfigCommand.Actions.LIST:
            for i in config.list_options():
                print(i)