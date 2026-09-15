"""Tests for ``simdb alias``."""

from unittest import mock

import pytest
from cli_helpers import make_simulation

LOCAL_ALIASES = ["hello", "world", "foo-123"]
REMOTE_ALIASES = ["foo#1", "bar", "barfoo", "123foo", "barbaz"]


@pytest.fixture
def aliases(local_db, remote_handshake):
    """A local database and a remote, each holding a known set of aliases."""
    local_db.list_simulations.return_value = [
        make_simulation(alias) for alias in LOCAL_ALIASES
    ]
    with mock.patch(
        "simdb.cli.remote_api.RemoteAPI.list_simulations",
        return_value=[make_simulation(alias) for alias in REMOTE_ALIASES],
    ), mock.patch("simdb.cli.remote_api.RemoteAPI.has_url", return_value=True):
        yield


def test_search_returns_local_and_remote_matches(invoke, aliases):
    result = invoke("alias", "search", "foo")

    assert result.exit_code == 0
    assert "\n".join(["foo#1", "barfoo", "123foo", "foo-123"]) in result.output


def test_search_without_matches_prints_nothing(invoke, aliases):
    result = invoke("alias", "search", "nothing-matches-this")

    assert result.exit_code == 0
    for alias in LOCAL_ALIASES + REMOTE_ALIASES:
        assert alias not in result.output


def test_list_shows_the_local_aliases(invoke, aliases):
    result = invoke("alias", "list")

    assert result.exit_code == 0
    assert "\n  ".join(LOCAL_ALIASES) in result.output


def test_list_with_a_remote_name_shows_both_sides(invoke, aliases):
    result = invoke("alias", "test", "list")

    assert result.exit_code == 0
    assert "\n  ".join(REMOTE_ALIASES) in result.output
    assert "\n  ".join(LOCAL_ALIASES) in result.output


def test_list_can_skip_the_remote(invoke, aliases):
    result = invoke("alias", "list", "--local")

    assert result.exit_code == 0
    assert "Remote:" not in result.output
    assert "\n  ".join(LOCAL_ALIASES) in result.output


def test_list_explains_a_remote_without_a_url(invoke, local_db, remote_handshake):
    local_db.list_simulations.return_value = []
    with mock.patch("simdb.cli.remote_api.RemoteAPI.has_url", return_value=False):
        result = invoke("alias", "list")

    assert result.exit_code == 0
    assert "The Remote Server has not been specified" in result.output


def test_make_unique_returns_an_unused_alias_unchanged(invoke, aliases):
    result = invoke("alias", "make-unique", "brand-new")

    assert result.exit_code == 0
    assert result.output.strip() == "brand-new"


def test_make_unique_appends_a_counter_to_a_taken_alias(invoke, aliases):
    result = invoke("alias", "make-unique", "bar")

    assert result.exit_code == 0
    assert result.output.strip() == "bar-1"


def test_make_unique_replaces_reserved_characters(invoke, aliases):
    result = invoke("alias", "make-unique", "a#b/c(d)e=f,g*h%i")

    assert result.exit_code == 0
    assert result.output.strip() == "a_b_c_d_e_f_g_h_i"


def test_make_unique_keeps_counting_past_a_taken_suffix(invoke, aliases, local_db):
    local_db.list_simulations.return_value = [
        make_simulation("bar"),
        make_simulation("bar-1"),
    ]

    result = invoke("alias", "make-unique", "bar")

    assert result.exit_code == 0
    assert result.output.strip() == "bar-2"


def test_the_group_shows_help_when_no_subcommand_is_given(invoke):
    result = invoke("alias")

    assert result.exit_code == 0
    assert "Query remote and local aliases." in result.output
    assert "make-unique" in result.output
