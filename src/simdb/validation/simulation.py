"""Validation of a simulation as a whole: its metadata and its data files.

The same checks run on the server for every API version, synchronously inside
the request in v1.2 and earlier and from a Celery worker for v1.3, so they are
kept here, independent of Flask.
"""

from typing import List

from simdb.config import Config, ConfigError
from simdb.database.models.simulation import Simulation
from simdb.validation.file import find_file_validator
from simdb.validation.report import FileReport, MetadataReport, ValidationReport
from simdb.validation.validator import ValidationError, Validator

VALIDATION_REPORT_KEY = "validation_report"
"""Metadata key under which the report of the last validation is stored.

The value is the dictionary form of a :class:`ValidationReport`.
"""


def validate_metadata(simulation: Simulation, config: Config) -> None:
    """Validate the metadata of SIMULATION against the configured schemas.

    :raise ValidationError: if the metadata does not satisfy a schema
    """
    for schema in Validator.validation_schemas(config, simulation):
        Validator(schema, config).validate(simulation)


def validate_files(simulation: Simulation, config: Config) -> List[FileReport]:
    """Validate the output files of SIMULATION with the configured file validator.

    Every output is checked, so the report covers all of them even when an
    early one fails. Does nothing unless ``file_validation.type`` names a
    validator.

    :return: the report of every file that was checked, failed or not
    :raise ConfigError: if ``file_validation.type`` names an unknown validator
    """
    validator_type = config.get_string_option("file_validation.type", default=None)
    if validator_type in (None, "none", ""):
        return []

    options = config.get_section("file_validation", default={})
    validator, validate_options = find_file_validator(validator_type, options)
    if validator is None:
        raise ConfigError(
            f"Invalid file validator specified in configuration: {validator_type}"
        )

    reports = []
    for output in simulation.outputs:
        try:
            report = validator.validate_uri(output.uri, validate_options)
        except ValidationError as err:
            report = FileReport(uri=str(output.uri), error=str(err))
        if report is not None:
            reports.append(report)
    return reports


def validate_simulation(simulation: Simulation, config: Config) -> ValidationReport:
    """Validate the metadata and then the output files of SIMULATION.

    Neither failure stops the other check, so the report always describes both.

    :raise ConfigError: if the validation configuration is invalid
    """
    try:
        validate_metadata(simulation, config)
    except ValidationError as err:
        metadata = MetadataReport(error=str(err))
    else:
        metadata = MetadataReport()

    return ValidationReport(metadata=metadata, files=validate_files(simulation, config))


def record_validation(simulation: Simulation, report: ValidationReport) -> None:
    """Store the outcome of a validation on SIMULATION.

    Sets the simulation status to passed or failed and keeps the report as
    structured metadata, so the result can be read back whether or not it
    passed.
    """
    simulation.status = (
        Simulation.Status.PASSED if report.passed else Simulation.Status.FAILED
    )
    simulation.set_meta(VALIDATION_REPORT_KEY, report.to_dict())
