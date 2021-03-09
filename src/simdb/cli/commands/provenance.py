import argparse
from typing import Any, Optional

from ._base import Command, _required_argument
from .query import QueryCommand
from ...config import Config
from ...docstrings import inherit_docstrings

import os
import yaml
import platform
import distro
from typing import Dict, Union, List, NewType


PlatformDetails = NewType('PlatformDetails', Dict[str, str])
EnvironmentDetails = NewType('EnvironmentDetails', Dict[str, Union[str, List[str]]])


def _platform_version() -> str:
    if platform.system() == 'Linux':
        return ' '.join(distro.linux_distribution()) + ' ' + platform.version()
    elif platform.system() == 'Darwin':
        return platform.mac_ver()[0] + ' ' + platform.version()
    elif platform.system() == 'Win':
        return ' '.join(platform.win32_ver())
    return 'Unknown'


def _platform_details() -> PlatformDetails:
    """

    :return:
    """
    data = PlatformDetails(dict(
        architecture=' '.join(platform.architecture()),
        libc_ver=' '.join(platform.libc_ver()),
        machine=platform.machine(),
        node=platform.node(),
        platform=platform.platform(),
        processor=platform.processor(),
        python_version=platform.python_version(),
        release=platform.release(),
        system=platform.system(),
        os_version=_platform_version()
    ))
    return data


def _environmental_vars() -> EnvironmentDetails:
    env_vars = EnvironmentDetails({})
    for (k, v) in os.environ.items():
        if 'PATH' in k:
            env_vars[k] = [i for i in v.split(os.pathsep) if i]
        else:
            env_vars[k] = v
    return env_vars


def _get_provenance() -> Dict[str, Union[PlatformDetails, EnvironmentDetails]]:
    prov: Dict[str, Union[PlatformDetails, EnvironmentDetails]] = dict(
        environment=_environmental_vars(),
        platform=_platform_details(),
    )
    return prov


def create_provenance_file(file_name: str) -> None:
    """Extract all the provenance for the current machine node and write this into a YAML file with the given file
    name.

    This makes use of the Python platform library to extract OS and hardware information.

    :param file_name: The name of the file to store the provenance YAML in.
    """
    with open(file_name, 'w') as file:
        yaml.dump(_get_provenance(), file, default_flow_style=False)


def read_provenance_file(file_name: str) -> Union[Dict, List, None]:
    """Read the given provenance YAML file and return the read data.

    :param file_name: The name of the file to read.
    :return: The YAML provenance data.
    """
    with open(file_name, 'r') as file:
        return yaml.load(file, Loader=yaml.SafeLoader)


@inherit_docstrings
class ProvenanceCommand(Command):
    """Command to work with provenance files -- create, ingest, query & print.
    """
    _help = "provenance tools"

    class CreateCommand(Command):
        _help = "create the provenance file from the current system"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("file", help="provenance file")

        def run(self, args: Any, _: Config) -> None:
            create_provenance_file(args.file)

    class IngestCommand(Command):
        _help = "ingest the provenance file"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")
            parser.add_argument("file", help="provenance file")

        def run(self, args: Any, config: Config) -> None:
            from ...database import get_local_db

            prov = read_provenance_file(args.file)
            db = get_local_db(config)
            db.insert_provenance(args.sim_id, prov)

    class PrintCommand(Command):
        _help = "print the provenance for a simulation"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

        def run(self, args: Any, config: Config) -> None:
            from ...database import get_local_db
            _required_argument(args, "ingest", "sim_id")
            db = get_local_db(config)
            prov = db.get_provenance(args.sim_id)
            print(str(prov))

    _commands = {
        "create": CreateCommand(),
        "ingest": IngestCommand(),
        "print": PrintCommand(),
        "query": QueryCommand(QueryCommand.QueryType.PROVENANCE),
    }

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        command_parsers = parser.add_subparsers(title="action", dest="action")
        command_parsers.required = True

        for name, command in self._commands.items():
            sub_parser = command_parsers.add_parser(name, help=command.help)
            command.add_arguments(sub_parser)

    class ProvenanceArgs(QueryCommand.QueryArgs):
        action: str
        file: Optional[str]
        sim_id: Optional[str]

    def run(self, args: ProvenanceArgs, config: Config) -> None:
        self._commands[args.action].run(args, config)