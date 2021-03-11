import argparse
from pathlib import Path

from uri import URI

from ._base import Command
from ...config import Config
from ...docstrings import inherit_docstrings


@inherit_docstrings
class ValidateCommand(Command):
    """Command to validate a recorded simulation.
    """
    _help = "validate the ingested simulation"

    class ValidateArgs(argparse.Namespace):
        sim_id: str

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("sim_id", metavar="uuid|alias", help="simulation UUID or alias")

    def run(self, args: ValidateArgs, config: Config) -> None:
        from itertools import chain
        from ...database import get_local_db
        from ...validation import ValidationError, Validator
        from ..manifest import DataObject

        db = get_local_db(config)
        simulation = db.get_simulation(args.sim_id)

        Validator().validate(simulation)

        for file in chain(simulation.inputs, simulation.outputs):
            if file.type == DataObject.Type.UDA:
                from ...uda.checksum import checksum as uda_checksum
                checksum = uda_checksum(file.uri)
            elif file.type == DataObject.Type.IMAS:
                from ...imas.checksum import checksum as imas_checksum
                checksum = imas_checksum(file.uri)
            elif file.type == DataObject.Type.FILE:
                from ...checksum import sha1_checksum
                checksum = sha1_checksum(file.uri.path)
            else:
                raise ValidationError("invalid checksum for file %s" % file.uri)

            if checksum != file.checksum:
                raise ValidationError("Checksum doest not match for file " + str(file))

        print("success")
