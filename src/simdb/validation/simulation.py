"""Validation of a simulation as a whole: its metadata and its data files.

The same checks run on the server for every API version, synchronously inside
the request in v1.2 and earlier and from a Celery worker for v1.3, so they are
kept here, independent of Flask.
"""

from dataclasses import dataclass
from typing import List

from simdb.config import Config, ConfigError
from simdb.database.models.simulation import Simulation
from simdb.validation.file import find_file_validator
from simdb.validation.validator import ValidationError, Validator

VALIDATION_REPORT_KEY = "validation_report"
"""Metadata key under which the report of the last validation is stored."""


@dataclass
class ValidationReport:
    """The outcome of validating a simulation."""

    passed: bool
    """Whether every check passed."""
    text: str
    """What was checked and the result of each check, for the user to read."""


def validate_metadata(simulation: Simulation, config: Config) -> None:
    """Validate the metadata of SIMULATION against the configured schemas.

    :raise ValidationError: if the metadata does not satisfy a schema
    """
    for schema in Validator.validation_schemas(config, simulation):
        Validator(schema, config).validate(simulation)


def validate_files(simulation: Simulation, config: Config) -> List[str]:
    """Validate the output files of SIMULATION with the configured file validator.

    Every output is checked, so the report covers all of them even when an
    early one fails. Does nothing unless ``file_validation.type`` names a
    validator.

    :return: the report of every file that was checked
    :raise ConfigError: if ``file_validation.type`` names an unknown validator
    :raise ValidationError: if any file fails validation; the message holds the
        reports of all checked files
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
    failed = False
    for output in simulation.outputs:
        try:
            report = validator.validate_uri(output.uri, validate_options)
        except ValidationError as err:
            failed = True
            reports.append(f"File {output.uri} failed validation:\n{err}")
        else:
            if report is not None:
                reports.append(f"File {output.uri} passed validation:\n{report}")

    if failed:
        raise ValidationError("\n\n".join(reports))
    return reports


def validate_simulation(simulation: Simulation, config: Config) -> ValidationReport:
    """Validate the metadata and then the output files of SIMULATION.

    Neither failure stops the other check, so the report always describes both.

    :raise ConfigError: if the validation configuration is invalid
    """
    sections = []
    passed = True

    try:
        validate_metadata(simulation, config)
    except ValidationError as err:
        passed = False
        sections.append(f"Metadata failed validation:\n{err}")
    else:
        sections.append("Metadata passed validation.")

    try:
        sections.extend(validate_files(simulation, config))
    except ValidationError as err:
        passed = False
        sections.append(str(err))

    return ValidationReport(passed=passed, text="\n\n".join(sections))


def record_validation(simulation: Simulation, report: ValidationReport) -> None:
    """Store the outcome of a validation on SIMULATION.

    Sets the simulation status to passed or failed and keeps the report as
    metadata, so the result can be read back whether or not it passed.
    """
    simulation.status = (
        Simulation.Status.PASSED if report.passed else Simulation.Status.FAILED
    )
    simulation.set_meta(VALIDATION_REPORT_KEY, report.text)
