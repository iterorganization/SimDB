"""Tests for the shared click parameter validators."""

import click
import pytest

from simdb.cli.commands.validators import validate_non_negative, validate_positive


@pytest.mark.parametrize("value", [0, 1, 100])
def test_non_negative_accepts_zero_and_above(value):
    assert validate_non_negative(None, None, value) == value


@pytest.mark.parametrize("value", [-1, -100])
def test_non_negative_rejects_negative_values(value):
    with pytest.raises(click.BadParameter, match="must be non-negative"):
        validate_non_negative(None, None, value)


@pytest.mark.parametrize("value", [1, 100])
def test_positive_accepts_values_above_zero(value):
    assert validate_positive(None, None, value) == value


@pytest.mark.parametrize("value", [0, -1])
def test_positive_rejects_zero_and_below(value):
    with pytest.raises(click.BadParameter, match="must be greater than zero"):
        validate_positive(None, None, value)
