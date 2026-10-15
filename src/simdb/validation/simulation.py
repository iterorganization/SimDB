"""Validation of a simulation as a whole: its metadata and its data files.

The same checks run on the server for every API version, synchronously inside
the request in v1.2 and earlier and from a Celery worker for v1.3, so they are
kept here, independent of Flask.
"""

from simdb.config import Config, ConfigError
from simdb.database.models.simulation import Simulation
from simdb.validation.file import find_file_validator
from simdb.validation.validator import Validator


def validate_metadata(simulation: Simulation, config: Config) -> None:
    """Validate the metadata of SIMULATION against the configured schemas.

    :raise ValidationError: if the metadata does not satisfy a schema
    """
    for schema in Validator.validation_schemas(config, simulation):
        Validator(schema, config).validate(simulation)


def validate_files(simulation: Simulation, config: Config) -> None:
    """Validate the output files of SIMULATION with the configured file validator.

    Does nothing unless ``file_validation.type`` names a validator.

    :raise ConfigError: if ``file_validation.type`` names an unknown validator
    :raise ValidationError: if a file fails validation
    """
    validator_type = config.get_string_option("file_validation.type", default=None)
    if validator_type in (None, "none", ""):
        return

    options = config.get_section("file_validation", default={})
    validator, validate_options = find_file_validator(validator_type, options)
    if validator is None:
        raise ConfigError(
            f"Invalid file validator specified in configuration: {validator_type}"
        )

    for output in simulation.outputs:
        validator.validate_uri(output.uri, validate_options)


def validate_simulation(simulation: Simulation, config: Config) -> None:
    """Validate the metadata and then the output files of SIMULATION.

    :raise ConfigError: if the validation configuration is invalid
    :raise ValidationError: on the first failed check
    """
    validate_metadata(simulation, config)
    validate_files(simulation, config)
