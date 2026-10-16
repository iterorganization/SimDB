from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from simdb.cli.manifest import Manifest
from simdb.config import Config, ConfigError
from simdb.database.models import Simulation
from simdb.imas.utils import SimDBUrl
from simdb.validation import (
    VALIDATION_REPORT_KEY,
    ValidationError,
    ValidationReport,
    record_validation,
    validate_files,
    validate_simulation,
)
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


@pytest.fixture
def file_validator():
    """A configured file validator that reports "ok" for every file."""
    validator = mock.MagicMock()
    validator.validate_uri.return_value = "ok"
    config = _config(
        **{"file_validation.type": "ids_validator", "file_validation.rulesets": "a"}
    )
    with mock.patch(
        "simdb.validation.simulation.find_file_validator",
        return_value=(validator, "options"),
    ) as find:
        yield validator, config, find


def test_validate_files_without_a_configured_validator():
    simulation = _simulation("imas:hdf5?path=/data/run")

    with mock.patch("simdb.validation.simulation.find_file_validator") as find:
        assert validate_files(simulation, _config()) == []

    find.assert_not_called()


def test_validate_files_with_an_unknown_validator():
    simulation = _simulation("imas:hdf5?path=/data/run")

    with pytest.raises(ConfigError, match="no_such_validator"):
        validate_files(
            simulation, _config(**{"file_validation.type": "no_such_validator"})
        )


def test_validate_files_reports_every_output(file_validator):
    validator, config, find = file_validator
    simulation = _simulation("imas:hdf5?path=/data/run", "imas:hdf5?path=/data/run2")

    reports = validate_files(simulation, config)

    find.assert_called_once_with(
        "ids_validator", {"type": "ids_validator", "rulesets": "a"}
    )
    assert validator.validate_uri.call_args_list == [
        mock.call(output.uri, "options") for output in simulation.outputs
    ]
    assert reports == [
        "File imas:hdf5?path=/data/run passed validation:\nok",
        "File imas:hdf5?path=/data/run2 passed validation:\nok",
    ]


def test_validate_files_skips_files_the_validator_does_not_check(file_validator):
    validator, config, _ = file_validator
    validator.validate_uri.return_value = None
    simulation = _simulation("file:///data/log.txt")

    assert validate_files(simulation, config) == []


def test_validate_files_checks_every_output_before_failing(file_validator):
    validator, config, _ = file_validator
    validator.validate_uri.side_effect = [ValidationError("rule X failed"), "ok"]
    simulation = _simulation("imas:hdf5?path=/data/run", "imas:hdf5?path=/data/run2")

    with pytest.raises(ValidationError) as excinfo:
        validate_files(simulation, config)

    assert validator.validate_uri.call_count == 2
    assert str(excinfo.value) == (
        "File imas:hdf5?path=/data/run failed validation:\nrule X failed\n\n"
        "File imas:hdf5?path=/data/run2 passed validation:\nok"
    )


def test_validate_simulation_reports_a_pass():
    with mock.patch("simdb.validation.simulation.validate_metadata"), mock.patch(
        "simdb.validation.simulation.validate_files", return_value=["File A ok"]
    ):
        report = validate_simulation(_simulation(), _config())

    assert report == ValidationReport(
        passed=True, text="Metadata passed validation.\n\nFile A ok"
    )


def test_validate_simulation_checks_files_despite_failing_metadata():
    with mock.patch(
        "simdb.validation.simulation.validate_metadata",
        side_effect=ValidationError("{'machine': ['required field']}"),
    ), mock.patch(
        "simdb.validation.simulation.validate_files", return_value=["File A ok"]
    ) as files:
        report = validate_simulation(_simulation(), _config())

    files.assert_called_once()
    assert report.passed is False
    assert report.text == (
        "Metadata failed validation:\n{'machine': ['required field']}\n\nFile A ok"
    )


def test_validate_simulation_reports_failing_files():
    with mock.patch("simdb.validation.simulation.validate_metadata"), mock.patch(
        "simdb.validation.simulation.validate_files",
        side_effect=ValidationError("File A failed validation:\nrule X"),
    ):
        report = validate_simulation(_simulation(), _config())

    assert report.passed is False
    assert report.text == (
        "Metadata passed validation.\n\nFile A failed validation:\nrule X"
    )


@pytest.mark.parametrize("passed", [True, False])
def test_record_validation_stores_status_and_report(passed):
    simulation = Simulation(Manifest())

    record_validation(simulation, ValidationReport(passed=passed, text="the report"))

    expected = Simulation.Status.PASSED if passed else Simulation.Status.FAILED
    assert simulation.status == expected
    assert simulation.meta_dict()[VALIDATION_REPORT_KEY] == "the report"


@pytest.fixture
def imas_validator():
    """Stand in for the imas-validator package, whether or not it is installed."""
    with mock.patch.object(
        ids_validator, "imas_validator_available", True
    ), mock.patch.object(
        ids_validator, "validate", create=True
    ) as validate, mock.patch.object(
        ids_validator, "_text_report", return_value="REPORT"
    ):
        validate.return_value.results = [mock.MagicMock(success=True)]
        yield validate


def test_ids_validator_skips_non_imas_files(imas_validator):
    report = IdsValidator().validate_uri(SimDBUrl("file:///data/log.txt"), "options")

    assert report is None
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
    report = IdsValidator().validate_uri(SimDBUrl(uri), "options")

    assert report == "REPORT"
    imas_validator.assert_called_once_with(
        imas_uri="imas:hdf5?path=/data/run", validate_options="options"
    )


def test_ids_validator_reports_the_failed_rules(imas_validator):
    imas_validator.return_value.results = [
        mock.MagicMock(success=True),
        mock.MagicMock(success=False),
    ]

    with pytest.raises(ValidationError, match=r"^REPORT$"):
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


def test_ids_validator_ignores_unset_list_options():
    pytest.importorskip("imas_validator")
    options = IdsValidator().configure({"type": "ids_validator"})

    assert options.rulesets == []
    assert options.extra_rule_dirs == []
    assert options.rule_filter.name == []
    assert options.rule_filter.ids == []
    assert options.use_bundled_rulesets is True
    assert options.apply_generic is True


def _rule_result(name, ids, success, msg="", nodes=()):
    return SimpleNamespace(
        success=success,
        msg=msg,
        rule=SimpleNamespace(name=name),
        idss=[(ids, 0)],
        nodes_dict={(ids, 0): set(nodes)},
    )


def test_text_report_lists_every_rule_with_a_few_nodes():
    nodes = [f"profiles_1d[{i}]/zeff" for i in range(12)]
    results = [
        _rule_result("generic/core_profiles.py:validate_zeff", "core_profiles", True),
        _rule_result(
            "generic/core_profiles.py:validate_zeff",
            "core_profiles",
            False,
            "zeff inconsistent",
            nodes,
        ),
        _rule_result("generic/generic.py:validate_time", "core_profiles", True),
        _rule_result("generic/generic.py:validate_time", "equilibrium", True),
        _rule_result(
            "generic/generic.py:validate_empty", "equilibrium", False, "", [""]
        ),
    ]
    collection = SimpleNamespace(results=results, imas_uri="imas:hdf5?path=/data/run")

    report = ids_validator._text_report(collection)

    assert report.startswith(
        "Tested URI : imas:hdf5?path=/data/run\n"
        "Number of tests carried out : 5\n"
        "Number of successful tests : 3\n"
        "Number of failed tests : 2\n"
    )
    core_profiles, equilibrium = report.split("\nFAILED IDS equilibrium occurrence 0\n")
    assert "\nFAILED IDS core_profiles occurrence 0\n" in core_profiles
    assert "  PASSED generic/generic.py:validate_time\n" in core_profiles
    assert (
        "  FAILED generic/core_profiles.py:validate_zeff: zeff inconsistent\n"
        in core_profiles
    )
    assert "    12 affected nodes: " in core_profiles
    assert "and 7 more\n" in core_profiles
    assert core_profiles.count("profiles_1d[") == 5
    assert equilibrium == (
        "  FAILED generic/generic.py:validate_empty: \n"
        "  PASSED generic/generic.py:validate_time\n"
    )
