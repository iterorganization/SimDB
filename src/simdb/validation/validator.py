import re
import warnings
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import cerberus
import numpy as np
import yaml

from simdb.config import Config, ConfigError
from simdb.database.models.simulation import Simulation
from simdb.remote.models import RangeValue

ValidatorBase = cast(Any, cerberus.Validator)


class TestParameters:
    pass


class LoadError(Exception):
    pass


class ValidationError(Exception):
    pass


class CustomValidator(ValidatorBase):
    types_mapping = cast(Any, cerberus.Validator).types_mapping.copy()
    types_mapping["numpy"] = cerberus.TypeDefinition("numpy", (np.ndarray,), ())

    def _validate_exists(self, check_exists, field, value):
        """The rule's arguments are validated against this schema:
        {'type': ['string'],
             'check_with': 'type'}"""
        if check_exists and not Path(value).exists():
            self._error(field, "File must exist")

    def _validate_min_value(self, min_value, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """

        if not isinstance(value, np.ndarray):
            value = value[~np.isnan(value)]
            if value.size == 0:
                self._error(field, "Values in numpy array are NaN or empty")
            self._error(field, "Value is not a numpy array")
        if min_value is not None and value.min() < min_value:
            self._error(field, f"Minimum {value.min()} less than {min_value}")

    def _validate_max_value(self, max_value, field, value):
        """The rule's arguments are validated against this schema:
        {'type': 'float'}
        """

        if not isinstance(value, np.ndarray):
            value = value[~np.isnan(value)]
            if value.size == 0:
                self._error(field, "Values in numpy array are NaN or empty")
            self._error(field, "Value is not a numpy array")
        if max_value is not None and value.max() > max_value:
            self._error(field, f"Maximum {value.max()} greater than {max_value}")

    def _compare(self, comparison, field, value, comparator: str, message: str):
        if comparison is None:
            return
        if isinstance(value, np.ndarray):
            if np.issubdtype(value.dtype, np.floating):
                value = value[~np.isnan(value)]
            if value.size == 0:
                self._error(field, "Values in numpy array are NaN or empty")
            if not getattr(value, comparator)(comparison).all():
                self._error(field, f"Values are not {message} {comparison}")
        elif isinstance(value, float):
            if not getattr(value, comparator)(comparison):
                self._error(field, f"Value is not {message} {comparison}")
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
        if isinstance(value, np.ndarray):
            return value
        elif isinstance(value, dict) and "min" in value and "max" in value:
            return np.array([value["min"], value["max"]], dtype=float)
        elif isinstance(value, RangeValue):
            return np.array([float(value.min), float(value.max)])
        elif isinstance(value, str):
            return np.fromstring(value[1:-1], sep=" ")
        else:
            return np.array(value)


def _load_schema(path: Union[Path, str]):
    path = Path(path)
    if not path.exists():
        warnings.warn(f"Validation schema not found: {path}", stacklevel=2)
        return {}

    with path.open() as file:
        try:
            schema = yaml.load(file, Loader=yaml.SafeLoader)
        except yaml.YAMLError as err:
            raise LoadError(
                f"Failed to read validation schema from file {path}"
            ) from err

    return schema


class Validator:
    _validator: CustomValidator
    _section_re = re.compile(r"\S+ \"(\S+)=(\S+)\"")

    @classmethod
    def validation_schemas(
        cls, config: Config, simulation: Optional[Simulation], path=None
    ) -> List[Dict]:
        configured_path = Path(
            str(
                config.get_option(
                    "validation.path", default=str(config.config_directory)
                )
            )
        )

        if not configured_path.is_file():
            raise ConfigError(
                f"validation.path '{configured_path}' is not a valid file. "
                "Set validation.path to the full path of your validation "
                "schema YAML file."
            )
        default_schema_path = configured_path

        paths = []
        if path:
            paths.append(path)
        else:
            paths.append(default_schema_path)

        # Look for config sections like [validation "key=value"] and see if the
        # simulationhas metadata matching the given test. If matching, adding the
        # "path" in this section to the paths.
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
                            path = config.get_section(section).get("path", "")
                            if path:
                                paths.append(path)
                elif section != "validation":
                    raise ConfigError(f"Invalid validation section {section}")

        schemas = []
        for path in paths:
            schemas.append(_load_schema(path))

        return schemas

    def _custom_validation_ext(self, config: Config):

        module_path = config.get_option("validation.custom_validator", default=None)
        if module_path is None:
            return CustomValidator

        if not isinstance(module_path, str):
            raise TypeError(
                "Expected 'custom_validator config value' to be a string, "
                f"got {type(module_path).__name__}"
            )

        if "." not in module_path:
            raise ValueError(
                f"Invalid validator path '{module_path}'."
                "Expected format: 'package.module.ClassName'"
            )

        module_name, class_name = module_path.rsplit(".", 1)

        try:
            module = import_module(module_name)
        except ModuleNotFoundError as err:
            raise ImportError(
                f"Unable to import module '{module_name}': {err}. "
                "Please ensure the necessary validation package is installed"
            ) from err
        try:
            validation_cls = getattr(module, class_name)
        except AttributeError as err:
            raise AttributeError(
                f"Module '{module_name}' does not have classor attribute '{class_name}'"
            ) from err
        return validation_cls

    def __init__(self, schema: Dict, config: Config):
        try:
            validation_cls = self._custom_validation_ext(config)
            self._validator = validation_cls(schema)
            self._validator.allow_unknown = True
        except cerberus.SchemaError as err:
            raise LoadError("Failed to parse validation schema") from err

    def validate(self, sim: Simulation) -> None:
        # convert sim to dictionary
        data = sim.meta_dict()
        # validate using cerberus
        if not self._validator.validate(data):
            raise ValidationError(self._validator.errors)
