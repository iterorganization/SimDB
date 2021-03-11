import argparse
from pathlib import Path

from ._base import Command
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class ManifestCommand(Command):
    """Command for working with manifest files.
    """
    _help = "create/check manifest file"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", choices=["check", "create"])
        parser.add_argument("manifest_file", help="manifest file location", type=Path)

    class ManifestArgs(argparse.Namespace):
        action: str
        manifest_file: Path

    def run(self, args: ManifestArgs, _: Config) -> None:
        from ..manifest import (Manifest, InvalidManifest)

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
