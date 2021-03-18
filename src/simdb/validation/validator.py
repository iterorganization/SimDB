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
        if min_value is not None and value.min() < min_value:
            self._error(field, "Minimum %s less than %s" % (value.min(), min_value))

    def _validate_max_value(self, max_value, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        if not isinstance(value, numpy.ndarray):
            self._error(field, "Value is not a numpy array")
        if max_value is not None and value.max() > max_value:
            self._error(field, "Maximum %s greater than %s" % (value.max(), max_value))

    def _compare(self, comparison, field, value, comparator: str, message: str):
        if comparison is None:
            return
        if isinstance(value, numpy.ndarray):
            if not getattr(value, comparator)(comparison).all():
                self._error(field, "Values are not %s %s" % (message, comparison))
        elif isinstance(value, float):
            if not getattr(value, comparator)(comparison):
                self._error(field, "Value is not %s %s" % (message, comparison))
        else:
            self._error(field, "Value is not a numpy array or a float")

    def _validate_gt(self, comparison, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        self._compare(comparison, field, value, '__gt__', 'greater than')

    def _validate_ge(self, comparison, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        self._compare(comparison, field, value, '__ge__', 'greater than or equal to')

    def _validate_lt(self, comparison, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        self._compare(comparison, field, value, '__lt__', 'less than')

    def _validate_le(self, comparison, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        self._compare(comparison, field, value, '__le__', 'less than or equal to')

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

    def __init__(self, schema: Dict):
        try:
            self._validator = CustomValidator(schema)
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
