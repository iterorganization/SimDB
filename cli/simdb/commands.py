import argparse

from .manifest import Manifest, InvalidManifest
from .database import Database


class Command:
    _help: str = NotImplemented

    @property
    def help(self):
        return type(self)._help

    def add_arguments(self, parser: argparse.ArgumentParser):
        raise NotImplementedError

    def run(self, args: argparse.Namespace):
        raise NotImplementedError


class IngestCommand(Command):
    _help = "ingest a manifest file"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("manifest_file", help="manifest file location")

    class IngestArgs(argparse.Namespace):
        manifest_file: str

    def run(self, args: IngestArgs):
        manifest = Manifest()
        manifest.load(args.manifest_file)
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

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("action", choices=["check", "create"])
        parser.add_argument("manifest_file", help="manifest file location")

    class ManifestArgs(argparse.Namespace):
        action: str
        manifest_file: str

    def run(self, args: ManifestArgs):
        manifest = Manifest()

        if args.action == "check":
            manifest.load(args.manifest_file)
            try:
                manifest.validate()
            except InvalidManifest as err:
                print(err)
                return
        elif args.action == "create":
            Manifest.from_template().save(args.manifest_file)
