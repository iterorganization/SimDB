from pathlib import Path
from unittest import mock

import pytest

from simdb.config import Config, ConfigError
from simdb.imas.utils import SimDBUrl
from simdb.validation import ValidationError, validate_files, validate_simulation
from simdb.validation.file import ids_validator
from simdb.validation.file.ids_validator import IdsValidator


def _config(**options) -> Config:
    config = Config()
    for key, value in options.items():
        config.set_option(key, value)
    return config


def _simulation(*output_uris: str):
    outputs = [mock.MagicMock(uri=SimDBUrl(uri)) for uri in output_uris]
    return mock.MagicMock(outputs=outputs)


def test_validate_files_without_a_configured_validator():
    simulation = _simulation("imas:hdf5?path=/data/run")

    with mock.patch("simdb.validation.simulation.find_file_validator") as find:
        validate_files(simulation, _config())

    find.assert_not_called()


def test_validate_files_with_an_unknown_validator():
    simulation = _simulation("imas:hdf5?path=/data/run")

    with pytest.raises(ConfigError, match="no_such_validator"):
        validate_files(
            simulation, _config(**{"file_validation.type": "no_such_validator"})
        )


def test_validate_files_validates_every_output():
    simulation = _simulation("imas:hdf5?path=/data/run", "file:///data/log.txt")
    config = _config(
        **{"file_validation.type": "ids_validator", "file_validation.rulesets": "a"}
    )
    validator = mock.MagicMock()

    with mock.patch(
        "simdb.validation.simulation.find_file_validator",
        return_value=(validator, "options"),
    ) as find:
        validate_files(simulation, config)

    find.assert_called_once_with(
        "ids_validator", {"type": "ids_validator", "rulesets": "a"}
    )
    assert validator.validate_uri.call_args_list == [
        mock.call(output.uri, "options") for output in simulation.outputs
    ]


def test_validate_simulation_checks_metadata_before_files():
    simulation = _simulation()
    config = _config()
    calls = []

    with mock.patch(
        "simdb.validation.simulation.validate_metadata",
        side_effect=lambda *_: calls.append("metadata"),
    ), mock.patch(
        "simdb.validation.simulation.validate_files",
        side_effect=lambda *_: calls.append("files"),
    ):
        validate_simulation(simulation, config)

    assert calls == ["metadata", "files"]


def test_validate_simulation_stops_at_failing_metadata():
    simulation = _simulation()

    with mock.patch(
        "simdb.validation.simulation.validate_metadata",
        side_effect=ValidationError("bad metadata"),
    ), mock.patch("simdb.validation.simulation.validate_files") as files:
        with pytest.raises(ValidationError, match="bad metadata"):
            validate_simulation(simulation, _config())

    files.assert_not_called()


@pytest.fixture
def imas_validator():
    """Stand in for the imas-validator package, whether or not it is installed."""
    with mock.patch.object(
        ids_validator, "imas_validator_available", True
    ), mock.patch.object(
        ids_validator, "validate", create=True
    ) as validate, mock.patch.object(
        ids_validator, "ValidationReportGenerator", create=True
    ) as report:
        validate.return_value.results = [mock.MagicMock(success=True)]
        report.return_value.txt = "REPORT"
        yield validate


def test_ids_validator_skips_non_imas_files(imas_validator):
    IdsValidator().validate_uri(SimDBUrl("file:///data/log.txt"), "options")

    imas_validator.assert_not_called()


@pytest.mark.parametrize(
    "uri",
    [
        "imas:hdf5?path=/data/run",
        "imas://uda.example.org:3090/uda?path=/data/run&backend=hdf5",
    ],
    ids=["local", "remote"],
)
def test_ids_validator_validates_the_local_dataset(imas_validator, uri):
    IdsValidator().validate_uri(SimDBUrl(uri), "options")

    imas_validator.assert_called_once_with(
        imas_uri="imas:hdf5?path=/data/run", validate_options="options"
    )


def test_ids_validator_reports_the_failed_rules(imas_validator):
    imas_validator.return_value.results = [
        mock.MagicMock(success=True),
        mock.MagicMock(success=False),
    ]

    with pytest.raises(ValidationError, match="REPORT"):
        IdsValidator().validate_uri(SimDBUrl("imas:hdf5?path=/data/run"), "options")


def test_ids_validator_reports_an_unreadable_dataset(imas_validator):
    imas_validator.side_effect = OSError("cannot open")

    with pytest.raises(ValidationError, match="cannot open"):
        IdsValidator().validate_uri(SimDBUrl("imas:hdf5?path=/data/run"), "options")


def test_ids_validator_rejects_a_uri_without_a_path(imas_validator):
    with pytest.raises(ValidationError, match="backend and path"):
        IdsValidator().validate_uri(SimDBUrl("imas:hdf5"), "options")

    imas_validator.assert_not_called()


def test_ids_validator_configures_from_the_server_section():
    pytest.importorskip("imas_validator")
    options = IdsValidator().configure(
        {
            "type": "ids_validator",
            "rulesets": "a,b",
            "extra_rule_dirs": "/rules",
            "rule_filter_ids": "summary",
            "bundled_ruleset": False,
        }
    )

    assert options.rulesets == ["a", "b"]
    assert options.extra_rule_dirs == [Path("/rules")]
    assert options.rule_filter.ids == ["summary"]
    assert options.use_bundled_rulesets is False
