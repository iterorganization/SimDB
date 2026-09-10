"""Tests for the console output helpers in ``simdb.cli.commands.utils``.

These are the functions that turn simulations and IDS quantities into what the
user actually sees. They are pure enough to call directly, so they are tested
here without going through a command.
"""

import pytest
from cli_helpers import make_simulation
from rich.console import Console

from simdb.cli.commands import utils
from simdb.cli.commands.utils import (
    is_numeric_1d,
    print_quantity,
    print_simulations,
    print_trace,
    show_quantity_textual_plot,
)
from simdb.remote.models import QuantityData, SimulationTraceData


@pytest.fixture(autouse=True)
def fixed_width_console(monkeypatch):
    """Give the rich output a stable width so assertions do not depend on the
    terminal the tests happen to run in."""
    monkeypatch.setattr(
        utils, "_RICH_CONSOLE", Console(width=120, legacy_windows=False)
    )


def quantity(data, name="grid/rho_tor_norm", units="-") -> QuantityData:
    return QuantityData(name=name, units=units, data=data)


# ---------------------------------------------------------------------------
# is_numeric_1d
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([1, 2, 3], True),
        ([1.0, 2.5], True),
        ([], False),
        ([[1, 2], [3, 4]], False),
        (["a", "b"], False),
        # bool is an int subclass, but plotting booleans is not what the caller
        # means by "numeric".
        ([True, False], False),
        (1.0, False),
        (None, False),
    ],
)
def test_is_numeric_1d(data, expected):
    assert is_numeric_1d(data) is expected


# ---------------------------------------------------------------------------
# print_quantity
# ---------------------------------------------------------------------------


def test_print_quantity_renders_a_scalar(capsys):
    print_quantity(quantity(1.23456789, name="time", units="s"))

    output = capsys.readouterr().out
    assert "1.23457" in output
    assert "scalar" in output


def test_print_quantity_renders_a_one_dimensional_array_with_stats(capsys):
    print_quantity(quantity([0.0, 0.5, 1.0]))

    output = capsys.readouterr().out
    assert "shape (3,)" in output
    for column in ("n", "min", "max", "mean", "std", "median"):
        assert column in output
    assert "0.5" in output


def test_print_quantity_truncates_long_rows(capsys):
    print_quantity(quantity(list(range(100))))

    output = capsys.readouterr().out
    assert "..." in output
    assert "shape (100,)" in output
    # Head and tail are kept, the middle is not.
    assert "0 1 2" in output
    assert "97 98 99" in output
    assert "50" not in output


def test_print_quantity_renders_a_two_dimensional_array(capsys):
    print_quantity(quantity([[1, 2], [3, 4]]))

    output = capsys.readouterr().out
    assert "shape (2, 2)" in output


def test_print_quantity_truncates_tall_two_dimensional_arrays(capsys):
    print_quantity(quantity([[row, row] for row in range(20)]))

    output = capsys.readouterr().out
    assert "shape (20, 2)" in output
    assert "..." in output


def test_print_quantity_summarises_higher_dimensional_arrays(capsys):
    print_quantity(quantity([[[1, 2], [3, 4]], [[5, 6], [7, 8]]]))

    output = capsys.readouterr().out
    assert "3-D array" in output


def test_print_quantity_can_omit_the_stats_table(capsys):
    print_quantity(quantity([0.0, 0.5, 1.0]), show_stats=False)

    output = capsys.readouterr().out
    assert "median" not in output


def test_print_quantity_uses_the_label_over_the_name(capsys):
    print_quantity(quantity([1, 2, 3], name="grid/rho_tor_norm"), label="field")

    output = capsys.readouterr().out
    assert "field" in output
    assert "rho_tor_norm" not in output


def test_print_quantity_falls_back_to_a_dash_for_missing_units(capsys):
    print_quantity(quantity(1.0, units=""))

    assert "[-]" in capsys.readouterr().out


def test_stats_are_omitted_for_a_single_value(capsys):
    print_quantity(quantity([42.0]))

    output = capsys.readouterr().out
    assert "shape (1,)" in output
    assert "median" not in output


# ---------------------------------------------------------------------------
# show_quantity_textual_plot
# ---------------------------------------------------------------------------


def test_plot_is_drawn_for_a_numeric_field(capsys):
    show_quantity_textual_plot(quantity([0.0, 1.0, 4.0, 9.0]), label="field")

    output = capsys.readouterr().out
    assert "index [-]" in output
    assert "shape (4,)" in output


def test_plot_uses_a_matching_coordinate_as_the_x_axis(capsys):
    show_quantity_textual_plot(
        quantity([0.0, 1.0, 4.0, 9.0]),
        label="field",
        x_quantity=quantity([0, 1, 2, 3], name="profiles_1d/time", units="s"),
    )

    output = capsys.readouterr().out
    assert "time [s]" in output
    assert "index [-]" not in output


def test_plot_ignores_a_coordinate_of_a_different_length(capsys):
    show_quantity_textual_plot(
        quantity([0.0, 1.0, 4.0]),
        x_quantity=quantity([0, 1], name="time", units="s"),
    )

    assert "index [-]" in capsys.readouterr().out


def test_non_numeric_data_is_printed_instead_of_plotted(capsys):
    show_quantity_textual_plot(quantity(["a", "b"]), label="field")

    output = capsys.readouterr().out
    assert "index [-]" not in output
    assert "shape (2,)" in output


# ---------------------------------------------------------------------------
# print_simulations
# ---------------------------------------------------------------------------


def test_print_simulations_reports_an_empty_list(capsys):
    print_simulations([])

    assert "No simulations found" in capsys.readouterr().out


def test_print_simulations_prints_a_single_alias_column(capsys):
    print_simulations([make_simulation("first"), make_simulation("second")])

    output = capsys.readouterr().out
    assert "alias" in output
    assert "first" in output
    assert "second" in output
    assert "UUID" not in output
    assert "status" not in output


def test_print_simulations_adds_datetime_and_status_when_verbose(capsys):
    print_simulations([make_simulation("first", status="passed")], verbose=True)

    output = capsys.readouterr().out
    assert "datetime" in output
    assert "status" in output
    assert "passed" in output


def test_print_simulations_adds_the_uuid_column_on_request(capsys):
    print_simulations([make_simulation("first", uuid="abcd1234")], show_uuid=True)

    output = capsys.readouterr().out
    assert "UUID" in output
    assert "abcd1234" in output


def test_print_simulations_adds_a_column_per_metadata_name(capsys):
    simulations = [
        make_simulation("first", meta={"pulse": 134173}),
        make_simulation("second", meta={}),
    ]

    print_simulations(simulations, metadata_names=["pulse"])

    output = capsys.readouterr().out
    assert "pulse" in output
    assert "134173" in output
    # A simulation without the metadata still gets a row.
    assert "second" in output


def test_print_simulations_handles_a_missing_alias(capsys):
    print_simulations([make_simulation(None, uuid="abcd1234")], show_uuid=True)

    assert "abcd1234" in capsys.readouterr().out


def test_print_simulations_hints_at_the_limit_when_a_full_page_is_returned(capsys):
    simulations = [make_simulation(f"sim{index}") for index in range(100)]

    print_simulations(simulations)

    assert "first 100 entries shown" in capsys.readouterr().out


def test_print_simulations_does_not_hint_below_the_limit(capsys):
    print_simulations([make_simulation(f"sim{index}") for index in range(99)])

    assert "first 100 entries shown" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"min": 1, "max": 5}, "[1, 5]"),
        ([1.0, 2.0], "[1.00, 2.00]"),
        ([True, False], "[True, False]"),
        (["a", "b"], "[a, b]"),
        # Long lists are truncated to five entries.
        (list(range(10)), "[0.00, 1.00, 2.00, 3.00, 4.00, ...]"),
        ("plain", "plain"),
    ],
)
def test_metadata_values_are_formatted_for_the_table(capsys, value, expected):
    print_simulations(
        [make_simulation("sim", meta={"field": value})], metadata_names=["field"]
    )

    assert expected in capsys.readouterr().out


# ---------------------------------------------------------------------------
# print_trace
# ---------------------------------------------------------------------------


def test_print_trace_reports_a_missing_trace(capsys):
    print_trace(None)

    assert "No simulations trace found" in capsys.readouterr().out


def test_print_trace_prints_the_simulation_and_its_status_date(capsys):
    trace = SimulationTraceData(
        alias="current", status="passed", passed_on="2024-01-01"
    )

    print_trace(trace)

    output = capsys.readouterr().out
    assert "current" in output
    assert "passed" in output
    assert "Passed on: 2024-01-01" in output


def test_print_trace_reports_an_unknown_status(capsys):
    print_trace(SimulationTraceData(alias="current"))

    assert "Status: unknown" in capsys.readouterr().out


def test_print_trace_indents_the_replaced_simulation(capsys):
    trace = SimulationTraceData(
        alias="current",
        status="passed",
        replaces=SimulationTraceData(alias="older", status="deprecated"),
        replaces_reason="superseded",
    )

    print_trace(trace)

    output = capsys.readouterr().out
    assert "Replaces: (reason: superseded)" in output
    assert "  Simulation:" in output
    assert "older" in output


def test_print_trace_handles_a_replacement_without_a_reason(capsys):
    trace = SimulationTraceData(
        alias="current", replaces=SimulationTraceData(alias="older")
    )

    print_trace(trace)

    output = capsys.readouterr().out
    assert "Replaces:" in output
    assert "reason" not in output
