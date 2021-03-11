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
        from ...imas import validation as imas_validation
        from ..manifest import DataObject

        db = get_local_db(config)
        simulation = db.get_simulation(args.sim_id)

        Validator().validate(simulation)

        # device = simulation.find_meta("device")
        # scenario = simulation.find_meta("scenario")
        # if not device:
        #     raise ValidationError("No device found in metadata")
        # if len(device) > 1:
        #     raise ValidationError("Multiple devices found in metadata")
        # if not scenario:
        #     raise ValidationError("No scenario found in metadata")
        # if len(device) > 1:
        #     raise ValidationError("Multiple scenarios found in metadata")
        # imas_names = set()
        # for file in chain(simulation.inputs, simulation.outputs):
        #     if file.type == DataObject.Type.UDA:
        #         from ...uda.checksum import checksum as uda_checksum
        #         uri = URI('uda:///?signal=%s&source=%s' % (file.file_name, file.directory))
        #         checksum = uda_checksum(uri)
        #     else:
        #         from ...checksum import sha1_checksum
        #         path = Path(file.directory) / file.file_name
        #         checksum = sha1_checksum(path)
        #     if checksum != file.checksum:
        #         raise ValidationError("Checksum doest not match for file " + str(file))
        #     if file.type == DataObject.Type.IMAS:
        #         imas_names.add(file.file_name.split(".")[0])
        # for name in imas_names:
        #     (tree, num) = name.split("_")
        #     shot = int(num[:-4])
        #     run = int(num[-4:])
        #     imas_obj = imas_validation.load_imas(shot, run)
        #     imas_validation.validate_imas(device[0].value, scenario[0].value, imas_obj)

        print("success")
