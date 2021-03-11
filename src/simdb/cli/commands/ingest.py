import argparse
from pathlib import Path
from typing import Optional

from ._base import Command
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class IngestCommand(Command):
    """Command to ingest simulation manifest files.
    """
    _help = "ingest a manifest file"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("manifest_file", help="manifest file location", type=Path)
        parser.add_argument("--alias", "-a", help="alias of an existing manifest to update, or a new alias use")
        parser.add_argument("--uuid", "-u", help="uuid of an already ingested manifest to update")
        parser.add_argument("--update", action="store_true", help="update an existing manifest")

    class IngestArgs(argparse.Namespace):
        manifest_file: Path
        alias: Optional[str]
        uuid: Optional[str]
        update: bool

    def run(self, args: IngestArgs, config: Config) -> None:
        from ...database import get_local_db
        from ...database.models import Simulation
        from ..manifest import Manifest

        manifest = Manifest()
        manifest.load(args.manifest_file)
        manifest.validate()
        # verify_metadata({}, manifest.metadata)

        simulation = Simulation(manifest)
        if args.alias:
            simulation.alias = args.alias
        if args.uuid:
            simulation.uuid = args.uuid

        db = get_local_db(config)
        db.insert_simulation(simulation)
        print(simulation.uuid)
