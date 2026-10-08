"""Tests for the IDS metadata helper used when pushing IMAS data."""

import pytest

from simdb.cli.remote_api import _meta_list


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # The list form written since #119.
        (["core_profiles", "equilibrium"], ["core_profiles", "equilibrium"]),
        (("core_profiles", "equilibrium"), ["core_profiles", "equilibrium"]),
        # The display string written by SimDB <= 1.2, which reaches the client
        # from a remote that has not been migrated.
        ("[core_profiles, equilibrium]", ["core_profiles", "equilibrium"]),
        ("core_profiles", ["core_profiles"]),
        # Nothing to filter on.
        (None, []),
        ("", []),
        ("[]", []),
    ],
)
def test_meta_list_normalises_both_stored_forms(value, expected):
    assert _meta_list(value) == expected


@pytest.mark.parametrize(
    "value", [["core_profiles", "equilibrium"], "[core_profiles, equilibrium]"]
)
def test_ids_names_match_however_the_value_was_stored(value):
    """push_simulation skips any IDS whose name is not in this list.

    Wrapping the display string instead of splitting it yields
    ``["[core_profiles, equilibrium]"]``, which matches no IDS name at all and so
    silently skips every file of the simulation.
    """
    ids_list = _meta_list(value)

    assert "core_profiles" in ids_list
    assert "equilibrium" in ids_list
    assert "core_sources" not in ids_list
