import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

from simdb.cli.manifest import Manifest
from simdb.config import Config, ConfigError
from simdb.database.models import Simulation
from simdb.imas.utils import SimDBUrl
from simdb.validation import (
    VALIDATION_REPORT_KEY,
    FileReport,
    IdsReport,
    MetadataReport,
    RuleReport,
    ValidationCounts,
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


def _passing_file(uri: str) -> FileReport:
    return FileReport(
        uri=uri,
        ids=[
            IdsReport("pf_active", 0, [RuleReport("coil_name", ValidationCounts(2, 0))])
        ],
    )


def _failing_file(uri: str) -> FileReport:
    return FileReport(
        uri=uri,
        ids=[
            IdsReport(
                "core_profiles",
                0,
                [
                    RuleReport("validate_time", ValidationCounts(3, 0)),
                    RuleReport(
                        "validate_zeff",
                        ValidationCounts(1, 2),
                        message="zeff inconsistent",
                        failed_nodes=12,
                        sample_nodes=["profiles_1d[0]/zeff", "profiles_1d[1]/zeff"],
                    ),
                ],
            ),
            IdsReport(
                "equilibrium", 0, [RuleReport("validate_time", ValidationCounts(1, 0))]
            ),
        ],
    )


@pytest.fixture
def file_validator():
    """A configured file validator that reports a pass for every file."""
    validator = mock.MagicMock()
    validator.validate_uri.side_effect = lambda uri, options: _passing_file(str(uri))
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
    assert [report.uri for report in reports] == [
        "imas:hdf5?path=/data/run",
        "imas:hdf5?path=/data/run2",
    ]
    assert all(report.passed for report in reports)


def test_validate_files_skips_files_the_validator_does_not_check(file_validator):
    validator, config, _ = file_validator
    validator.validate_uri.side_effect = None
    validator.validate_uri.return_value = None
    simulation = _simulation("file:///data/log.txt")

    assert validate_files(simulation, config) == []


def test_validate_files_records_a_file_that_cannot_be_validated(file_validator):
    validator, config, _ = file_validator
    validator.validate_uri.side_effect = [
        ValidationError("cannot open"),
        _passing_file("imas:hdf5?path=/data/run2"),
    ]
    simulation = _simulation("imas:hdf5?path=/data/run", "imas:hdf5?path=/data/run2")

    reports = validate_files(simulation, config)

    assert validator.validate_uri.call_count == 2
    assert reports[0] == FileReport(uri="imas:hdf5?path=/data/run", error="cannot open")
    assert reports[0].passed is False
    assert reports[1].passed is True


def test_validate_simulation_reports_a_pass():
    files = [_passing_file("imas:hdf5?path=/data/run")]
    with mock.patch("simdb.validation.simulation.validate_metadata"), mock.patch(
        "simdb.validation.simulation.validate_files", return_value=files
    ):
        report = validate_simulation(_simulation(), _config())

    assert report == ValidationReport(metadata=MetadataReport(), files=files)
    assert report.passed is True
    assert report.tests == ValidationCounts(2, 0)


def test_validate_simulation_checks_files_despite_failing_metadata():
    files = [_passing_file("imas:hdf5?path=/data/run")]
    with mock.patch(
        "simdb.validation.simulation.validate_metadata",
        side_effect=ValidationError("{'machine': ['required field']}"),
    ), mock.patch(
        "simdb.validation.simulation.validate_files", return_value=files
    ) as validate:
        report = validate_simulation(_simulation(), _config())

    validate.assert_called_once()
    assert report.passed is False
    assert report.metadata == MetadataReport(error="{'machine': ['required field']}")
    assert report.files == files


def test_validate_simulation_reports_failing_files():
    files = [_failing_file("imas:hdf5?path=/data/run")]
    with mock.patch("simdb.validation.simulation.validate_metadata"), mock.patch(
        "simdb.validation.simulation.validate_files", return_value=files
    ):
        report = validate_simulation(_simulation(), _config())

    assert report.passed is False
    assert report.metadata.passed is True
    assert report.tests == ValidationCounts(5, 2)


@pytest.mark.parametrize("passed", [True, False])
def test_record_validation_stores_status_and_report(passed):
    simulation = Simulation(Manifest())
    report = ValidationReport(
        metadata=MetadataReport(error=None if passed else "missing machine")
    )

    record_validation(simulation, report)

    expected = Simulation.Status.PASSED if passed else Simulation.Status.FAILED
    assert simulation.status == expected
    assert simulation.meta_dict()[VALIDATION_REPORT_KEY] == report.to_dict()


def test_report_dict_has_the_outcome_and_counts_at_every_level():
    report = ValidationReport(
        metadata=MetadataReport(),
        files=[_failing_file("imas:hdf5?path=/data/run")],
    )

    data = report.to_dict()

    assert data["passed"] is False
    assert data["tests"] == {"total": 7, "passed": 5, "failed": 2}
    assert data["metadata"] == {"passed": True, "error": None}
    (file,) = data["files"]
    assert file["uri"] == "imas:hdf5?path=/data/run"
    assert file["passed"] is False
    assert file["error"] is None
    assert file["tests"] == {"total": 7, "passed": 5, "failed": 2}
    core_profiles, equilibrium = file["ids"]
    assert core_profiles["name"] == "core_profiles"
    assert core_profiles["occurrence"] == 0
    assert core_profiles["passed"] is False
    assert core_profiles["tests"] == {"total": 6, "passed": 4, "failed": 2}
    assert core_profiles["rules"][1] == {
        "name": "validate_zeff",
        "passed": False,
        "tests": {"total": 3, "passed": 1, "failed": 2},
        "message": "zeff inconsistent",
        "failed_nodes": 12,
        "sample_nodes": ["profiles_1d[0]/zeff", "profiles_1d[1]/zeff"],
    }
    assert equilibrium["passed"] is True


def test_report_text_lists_every_rule_with_a_few_nodes():
    report = ValidationReport(
        metadata=MetadataReport(),
        files=[
            _failing_file("imas:hdf5?path=/data/run"),
            FileReport(uri="file:///data/other", error="cannot open"),
        ],
    )

    assert report.text == (
        "Metadata passed validation.\n"
        "\n"
        "File imas:hdf5?path=/data/run failed validation:\n"
        "Number of tests carried out : 7\n"
        "Number of successful tests : 5\n"
        "Number of failed tests : 2\n"
        "\n"
        "FAILED IDS core_profiles occurrence 0\n"
        "  PASSED validate_time\n"
        "  FAILED validate_zeff: zeff inconsistent\n"
        "    12 affected nodes: profiles_1d[0]/zeff, profiles_1d[1]/zeff and 10 more\n"
        "\n"
        "PASSED IDS equilibrium occurrence 0\n"
        "  PASSED validate_time\n"
        "\n"
        "File file:///data/other could not be validated:\n"
        "cannot open"
    )


def test_report_text_of_a_failed_metadata_check():
    report = ValidationReport(metadata=MetadataReport(error="{'machine': [...]}"))

    assert report.text == "Metadata failed validation:\n{'machine': [...]}"


def test_report_of_a_validation_that_could_not_run():
    report = ValidationReport(error="RuntimeError: IMAS-validator not available")

    assert report.passed is False
    assert report.to_dict()["error"] == "RuntimeError: IMAS-validator not available"
    assert report.text == (
        "Validation could not be carried out:\n"
        "RuntimeError: IMAS-validator not available"
    )


def _rule_result(name, ids, success, msg="", nodes=(), exc=None):
    """An IDSValidationResult as the validator's ResultCollector builds it.

    ``assert_`` records the rule's message with ``exc=None``; a rule that raised
    is recorded by ``add_error_result`` with an empty message and the exception
    in ``exc``. Occurrences are numpy integers.
    """
    occurrence = np.int32(0)
    return SimpleNamespace(
        success=success,
        msg=msg,
        rule=SimpleNamespace(name=name),
        idss=[(ids, occurrence)],
        nodes_dict={(ids, occurrence): set(nodes)},
        exc=exc,
    )


@pytest.fixture
def imas_validator():
    """Stand in for the imas-validator package, whether or not it is installed."""
    with mock.patch.object(
        ids_validator, "imas_validator_available", True
    ), mock.patch.object(ids_validator, "validate", create=True) as validate:
        validate.return_value = SimpleNamespace(
            results=[_rule_result("rule_a", "pf_active", True)]
        )
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

    assert report == FileReport(
        uri=uri,
        ids=[IdsReport("pf_active", 0, [RuleReport("rule_a", ValidationCounts(1, 0))])],
    )
    assert report.passed is True
    imas_validator.assert_called_once_with(
        imas_uri="imas:hdf5?path=/data/run", validate_options="options"
    )


def test_ids_validator_reports_the_failed_rules(imas_validator):
    imas_validator.return_value.results = [
        _rule_result("rule_a", "pf_active", True),
        _rule_result("rule_a", "pf_active", False, "bad coil", ["coil[0]/name"]),
    ]

    report = IdsValidator().validate_uri(
        SimDBUrl("imas:hdf5?path=/data/run"), "options"
    )

    assert report.passed is False
    (rule,) = report.ids[0].rules
    assert rule == RuleReport(
        "rule_a",
        ValidationCounts(1, 1),
        message="bad coil",
        failed_nodes=1,
        sample_nodes=["coil[0]/name"],
    )


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


def test_file_report_fails_the_file_for_a_failure_without_an_ids():
    """A rule that crashed before it was bound to an IDS still fails the file,
    without discarding the other rules that ran."""
    unbound = SimpleNamespace(
        success=False,
        msg="",
        rule=SimpleNamespace(name="rule_x"),
        idss=[],
        nodes_dict={},
        exc=IndexError("list index out of range"),
    )
    collection = SimpleNamespace(
        results=[_rule_result("rule_a", "pf_active", True), unbound]
    )

    report = ids_validator._file_report("imas:hdf5?path=/data/run", collection)

    assert report.passed is False
    assert report.error == "rule_x: IndexError: list index out of range"
    assert len(report.ids) == 1
    assert report.ids[0].name == "pf_active"
    assert report.ids[0].passed is True


def test_file_report_names_the_exception_of_a_crashed_rule():
    """A rule that raised has no message, so the exception is the reason."""
    results = [
        _rule_result("rule_a", "pf_active", True),
        _rule_result("rule_a", "pf_active", False, exc=KeyError("profiles_1d[0]/zeff")),
    ]
    collection = SimpleNamespace(results=results)

    report = ids_validator._file_report("imas:hdf5?path=/data/run", collection)

    (rule,) = report.ids[0].rules
    assert rule.passed is False
    assert rule.message == "KeyError: 'profiles_1d[0]/zeff'"
    assert "FAILED rule_a: KeyError: 'profiles_1d[0]/zeff'" in report.text


def test_file_report_prefers_the_rule_message_over_the_exception():
    result = _rule_result("rule_a", "pf_active", False, "bad coil", exc=ValueError())
    collection = SimpleNamespace(results=[result])

    report = ids_validator._file_report("imas:hdf5?path=/data/run", collection)

    assert report.ids[0].rules[0].message == "bad coil"


def test_file_report_groups_results_per_ids_and_rule():
    nodes = [f"profiles_1d[{i}]/zeff" for i in range(12)]
    results = [
        _rule_result("validate_zeff", "core_profiles", True),
        _rule_result(
            "validate_zeff", "core_profiles", False, "zeff inconsistent", nodes
        ),
        _rule_result("validate_time", "core_profiles", True),
        _rule_result("validate_time", "equilibrium", True),
        _rule_result("validate_empty", "equilibrium", False, "", [""]),
    ]
    collection = SimpleNamespace(results=results, imas_uri="imas:hdf5?path=/data/run")

    report = ids_validator._file_report("imas:hdf5?path=/data/run", collection)

    assert report.tests == ValidationCounts(3, 2)
    json.dumps(report.to_dict())  # no numpy types left behind
    core_profiles, equilibrium = report.ids
    assert type(core_profiles.occurrence) is int
    assert (core_profiles.name, core_profiles.occurrence) == ("core_profiles", 0)
    zeff = next(rule for rule in core_profiles.rules if rule.name == "validate_zeff")
    assert zeff.tests == ValidationCounts(1, 1)
    assert zeff.message == "zeff inconsistent"
    assert zeff.failed_nodes == 12
    assert len(zeff.sample_nodes) == ids_validator.NODES_SHOWN
    assert set(zeff.sample_nodes) < set(nodes)
    empty = next(rule for rule in equilibrium.rules if rule.name == "validate_empty")
    assert empty.passed is False
    assert empty.failed_nodes == 0
    assert empty.sample_nodes == []
