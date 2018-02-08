import argparse


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
