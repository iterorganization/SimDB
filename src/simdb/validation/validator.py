import cerberus
import yaml
import appdirs
from pathlib import Path
from ..database.models import Simulation


class TestParameters:
    pass


class LoadError(Exception):
    pass


class ValidationError(Exception):
    pass


class CustomValidator(cerberus.Validator):
    def _validate_exists(self, check_exists, field, value):
        """ The rule's arguments are validated against this schema:
        {'type': ['string'],
             'check_with': 'type'} """
        if check_exists and not Path(value).exists():
            self._error(field, "File must exist")

    def _validate_checksum(self, check_checksum, field, value):
        """ The rule's arguments are validated against this schema:
        {'type': ['string'],
             'check_with': 'type'} """
        if check_checksum and False:
            self._error(field, "File checksum must be valid")


class Validator:

    _validator: cerberus.Validator

    def __init__(self, path=None):
        if path is None:
            path = Path(appdirs.user_config_dir('simdb')) / 'validation-schema.yaml'

        if not path.exists():
            self._validator = CustomValidator({})
            return

        # load schema from file
        with open(path, 'r') as file:
            try:
                schema = yaml.load(file, Loader=yaml.SafeLoader)
            except yaml.YAMLError:
                raise LoadError("Failed to read validation schema from file %s" % file)
        try:
            self._validator = CustomValidator(schema)
        except cerberus.SchemaError:
            raise LoadError("Failed to parse validation schema from file %s" % file)

    def validate(self, sim: Simulation):
        # convert sim to dictionary
        data = sim.data(recurse=True)
        # validate using cerberus
        self._validator.validate(data)
