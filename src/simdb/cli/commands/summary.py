import argparse
import os
from typing import Any

from ._base import Command, _flatten_dict, _list_summaries
from .query import QueryCommand
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class SummaryCommand(Command):
    """Command for processing summary IDSs and recording them against a simulation.
    """
    _help = "create and ingest IMAS summaries"

    class SummaryCreateCommand(Command):
        _help = "create the summary file"
        _script = "/work/imas/extra/bin/create_db_entry"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("file", help="file to create")
            parser.add_argument("shot", help="IDS shot")
            parser.add_argument("run", help="IDS run")

        def run(self, args: Any, _: Config) -> None:
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

        def run(self, args: Any, config: Config) -> None:
            from ...database import get_local_db
            import yaml

            with open(args.file) as f:
                y = yaml.safe_load(f)
                summary = _flatten_dict(y)
            db = get_local_db(config)
            db.insert_summary(args.sim_id, summary)

    class SummaryListCommand(Command):
        _help = "list the ingested summaries"

        def add_arguments(self, parser: argparse.ArgumentParser):
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

        class SummaryListArgs(argparse.Namespace):
            sim_id: str

        def run(self, args: SummaryListArgs, config: Config) -> None:
            from ...database import get_local_db

            db = get_local_db(config)
            summaries = db.list_summaries(args.sim_id)
            _list_summaries(summaries)

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

    class SummaryArgs:
        sum_action: str

    def run(self, args: SummaryArgs, config: Config) -> None:
        self._commands[args.sum_action].run(args, config)