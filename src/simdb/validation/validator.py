import cerberus
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional

from ..database.models.simulation import Simulation
from ..config import Config, ConfigError


class TestParameters:
    pass


class LoadError(Exception):
    pass


class ValidationError(Exception):
    pass


class CustomValidator(cerberus.Validator):
    import numpy as np

    types_mapping = cerberus.Validator.types_mapping.copy()
    types_mapping["numpy"] = cerberus.TypeDefinition("numpy", (np.ndarray,), ())

    def _validate_exists(self, check_exists, field, value):
        """The rule's arguments are validated against this schema:
        {'type': ['string'],
             'check_with': 'type'}"""
        if check_exists and not Path(value).exists():
            self._error(field, "File must exist")

    def _validate_checksum(self, check_checksum, field, value):
        """The rule's arguments are validated against this schema:
        {'type': ['string'],
             'check_with': 'type'}"""
        if check_checksum and False:
            self._error(field, "File checksum must be valid")

    def _validate_min_value(self, min_value, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        import numpy as np

        if not isinstance(value, np.ndarray):
            self._error(field, "Value is not a numpy array")
        if min_value is not None and value.min() < min_value:
            self._error(field, "Minimum %s less than %s" % (value.min(), min_value))

    def _validate_max_value(self, max_value, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        import numpy as np

        if not isinstance(value, np.ndarray):
            self._error(field, "Value is not a numpy array")
        if max_value is not None and value.max() > max_value:
            self._error(field, "Maximum %s greater than %s" % (value.max(), max_value))

    def _compare(self, comparison, field, value, comparator: str, message: str):
        import numpy as np

        if comparison is None:
            return
        if isinstance(value, np.ndarray):
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
        self._compare(comparison, field, value, "__gt__", "greater than")

    def _validate_ge(self, comparison, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        self._compare(comparison, field, value, "__ge__", "greater than or equal to")

    def _validate_lt(self, comparison, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        self._compare(comparison, field, value, "__lt__", "less than")

    def _validate_le(self, comparison, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """
        self._compare(comparison, field, value, "__le__", "less than or equal to")

    @classmethod
    def _normalize_coerce_int(cls, value):
        return int(value)

    @classmethod
    def _normalize_coerce_float(cls, value):
        return float(value)

    @classmethod
    def _normalize_coerce_numpy(cls, value):
        import numpy as np

        if isinstance(value, np.ndarray):
            return value
        elif isinstance(value, str):
            return np.fromstring(value[1:-1], sep=" ")
        else:
            return np.array(value)


def _load_schema(path: Path):
    if not path.exists():
        return [{}]

    # load schema from file
    with open(path, "r") as file:
        try:
            schema = yaml.load(file, Loader=yaml.SafeLoader)
            return schema
        except yaml.YAMLError:
            raise LoadError("Failed to read validation schema from file %s" % file)


class Validator:
    _validator: cerberus.Validator
    _section_re = re.compile(r"\S+ \"(\S+)=(\S+)\"")

    @classmethod
    def validation_schemas(
        cls, config: Config, simulation: Optional[Simulation], path=None
    ) -> List[Dict]:
        root = Path(
            str(
                config.get_option(
                    "validation.path", default=str(config.config_directory)
                )
            )
        )

        paths = []
        if path:
            paths.append(path)
        else:
            paths.append(root / "validation-schema.yaml")

        # Look for config sections like [validation "key=value"] and see if the simulation has metadata matching the
        # given test. If matching, adding the "path" in this section to the paths.
        if simulation is not None:
            sections = [
                sec for sec in config.sections() if sec.startswith("validation")
            ]
            for section in sections:
                if section == "validation":
                    continue
                match = cls._section_re.match(section)
                if match:
                    key = match.group(1)
                    value = match.group(2)
                    for meta in simulation.find_meta(key):
                        if meta.value == value:
                            path = config.get_section(section).get("path", default="")
                            if path:
                                paths.append(path)
                elif section != "validation":
                    raise ConfigError(f"Invalid validation section {section}")

        schemas = []
        for path in paths:
            schemas.append(_load_schema(path))

        return schemas

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
