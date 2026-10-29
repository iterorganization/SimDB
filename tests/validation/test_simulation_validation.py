import json
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

from simdb.imas.utils import SimDBUrl
from simdb.validation import (
    FileReport,
    IdsReport,
    RuleReport,
    ValidationCounts,
)
from simdb.validation.file import ids_validator
from simdb.validation.file.ids_validator import IdsValidator

URI = "imas:hdf5?path=/data/run"


def _rule_result(name, ids, success, msg="", nodes=(), exc=None):
    """An IDSValidationResult as the validator's ResultCollector builds it.

    ``assert_`` records the rule's message with ``exc=None``; a rule that raised
    is recorded by ``add_error_result`` with an empty message and the exception
    in ``exc``. Occurrences are numpy integers.
    """
    key = (ids, np.int32(0))
    return SimpleNamespace(
        success=success,
        msg=msg,
        rule=SimpleNamespace(name=name),
        idss=[key],
        nodes_dict={key: set(nodes)},
        exc=exc,
    )


def _file_report(*results):
    return ids_validator._file_report(URI, SimpleNamespace(results=list(results)))


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


@pytest.mark.parametrize(
    "uri",
    [URI, "imas://uda.example.org:3090/uda?path=/data/run&backend=hdf5"],
    ids=["local", "remote"],
)
def test_ids_validator_validates_the_local_dataset(imas_validator, uri):
    report = IdsValidator().validate_uri(SimDBUrl(uri), "options")

    rule = RuleReport("rule_a", ValidationCounts(1, 0))
    assert report == FileReport(uri=uri, ids=[IdsReport("pf_active", 0, [rule])])
    imas_validator.assert_called_once_with(imas_uri=URI, validate_options="options")


def test_file_report_groups_results_per_ids_and_rule():
    nodes = [f"profiles_1d[{i}]/zeff" for i in range(12)]
    report = _file_report(
        _rule_result("validate_zeff", "core_profiles", True),
        _rule_result("validate_zeff", "core_profiles", False, "zeff bad", nodes),
        _rule_result("validate_time", "core_profiles", True),
        _rule_result("validate_time", "equilibrium", True),
        _rule_result("validate_empty", "equilibrium", False, "", [""]),
    )

    assert report.tests == ValidationCounts(3, 2)
    json.dumps(report.to_dict())  # no numpy types left behind
    core_profiles, equilibrium = report.ids
    assert type(core_profiles.occurrence) is int
    assert (core_profiles.name, core_profiles.occurrence) == ("core_profiles", 0)
    zeff = next(rule for rule in core_profiles.rules if rule.name == "validate_zeff")
    assert (zeff.tests, zeff.message) == (ValidationCounts(1, 1), "zeff bad")
    assert zeff.failed_nodes == 12
    assert len(zeff.sample_nodes) == ids_validator.NODES_SHOWN
    assert set(zeff.sample_nodes) < set(nodes)
    empty = next(rule for rule in equilibrium.rules if rule.name == "validate_empty")
    assert (empty.passed, empty.failed_nodes, empty.sample_nodes) == (False, 0, [])


@pytest.mark.parametrize(
    "msg, message",
    [("", "KeyError: 'zeff'"), ("bad zeff", "bad zeff")],
    ids=["exception", "rule-message"],
)
def test_file_report_explains_a_failed_rule(msg, message):
    """A rule that raised has no message, so the exception is the reason."""
    report = _file_report(
        _rule_result("rule_a", "pf_active", True),
        _rule_result("rule_a", "pf_active", False, msg, exc=KeyError("zeff")),
    )

    (rule,) = report.ids[0].rules
    assert rule.passed is False
    assert rule.message == message
    assert f"FAILED rule_a: {message}" in report.text


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

    report = _file_report(_rule_result("rule_a", "pf_active", True), unbound)

    assert report.passed is False
    assert report.error == "rule_x: IndexError: list index out of range"
    assert [(ids.name, ids.passed) for ids in report.ids] == [("pf_active", True)]
