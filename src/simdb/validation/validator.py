import cerberus
import yaml
import appdirs
import numpy
from pathlib import Path
from ..database.models import Simulation
from typing import Dict


class TestParameters:
    pass


class LoadError(Exception):
    pass


class ValidationError(Exception):
    pass


numpy_type = cerberus.TypeDefinition('numpy', (numpy.ndarray,), ())


class CustomValidator(cerberus.Validator):
    types_mapping = cerberus.Validator.types_mapping.copy()
    types_mapping['numpy'] = numpy_type

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

    def _validate_min_value(self, min_value, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        if not isinstance(value, numpy.ndarray):
            self._error(field, "Value is not a numpy array")
        if min_value and value.min() < min_value:
            self._error(field, "Minimum %s less than %s" % (value.min(), min_value))

    def _validate_max_value(self, max_value, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        if not isinstance(value, numpy.ndarray):
            self._error(field, "Value is not a numpy array")
        if max_value and value.min() > max_value:
            self._error(field, "Maximum %s greater than %s" % (value.max(), max_value))

    @classmethod
    def _normalize_coerce_int(cls, value):
        return int(value)

    @classmethod
    def _normalize_coerce_float(cls, value):
        return float(value)

    @classmethod
    def _normalize_coerce_numpy(cls, value):
        return numpy.fromstring(value[1:-1], sep=' ')


class Validator:

    _validator: cerberus.Validator

    @classmethod
    def validation_schema(cls, path=None) -> Dict:
        if path is None:
            path = Path(appdirs.user_config_dir('simdb')) / 'validation-schema.yaml'

        if not path.exists():
            return {}

        # load schema from file
        with open(path, 'r') as file:
            try:
                schema = yaml.load(file, Loader=yaml.SafeLoader)
                return schema
            except yaml.YAMLError:
                raise LoadError("Failed to read validation schema from file %s" % file)

    def __init__(self, path=None):
        try:
            self._validator = CustomValidator(self.validation_schema(path))
            self._validator.allow_unknown = True
        except cerberus.SchemaError:
            raise LoadError("Failed to parse validation schema")

    def validate(self, sim: Simulation) -> None:
        # convert sim to dictionary
        data = sim.meta_dict()
        # data = sim.data(recurse=True)
        # validate using cerberus
        if not self._validator.validate(data):
            raise ValidationError(self._validator.errors)
