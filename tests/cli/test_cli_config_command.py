"""Tests for ``simdb config``."""

from unittest import mock

import pytest

from simdb.cli.simdb import cli


def test_get_prints_the_option_value(invoke):
    with mock.patch(
        "simdb.config.config.Config.get_option", return_value="bar"
    ) as get_option:
        result = invoke("config", "get", "foo")

    assert result.exit_code == 0
    assert "bar" in result.output
    # Config.load also reads options, so only the final call is the command's.
    assert get_option.call_args.args == ("foo",)


def test_get_reads_from_the_loaded_config_file(invoke):
    result = invoke("config", "get", "remote.test.url")

    assert result.exit_code == 0
    assert "http://0.0.0.0:5000/" in result.output


def test_get_fails_for_an_unknown_option(invoke):
    result = invoke("config", "get", "no.such.option")

    assert result.exit_code != 0


def test_set_stores_the_option_and_saves(invoke):
    with mock.patch("simdb.config.config.Config.save") as save, mock.patch(
        "simdb.config.config.Config.set_option"
    ) as set_option:
        result = invoke("config", "set", "foo", "bar")

    assert result.exit_code == 0
    # Config.load sets options for the SIMDB_* environment variables first.
    assert set_option.call_args.args == ("foo", "bar")
    assert save.called


def test_delete_removes_the_option_and_saves(invoke):
    with mock.patch("simdb.config.config.Config.save") as save, mock.patch(
        "simdb.config.config.Config.delete_option"
    ) as delete_option:
        result = invoke("config", "delete", "foo")

    assert result.exit_code == 0
    assert "Success." in result.output
    delete_option.assert_called_once_with("foo")
    assert save.called


def test_list_shows_the_configured_options(invoke):
    result = invoke("config", "list")

    assert result.exit_code == 0
    assert "remote.test.url: http://0.0.0.0:5000/" in result.output


def test_list_masks_remote_tokens(invoke):
    """A token in the configuration must never be echoed back in full."""
    result = invoke("config", "list")

    assert result.exit_code == 0
    assert "remote.test.token: ********" in result.output
    assert "123ABC" not in result.output


def test_path_prints_the_config_file_that_was_loaded(invoke, tmp_path):
    """``--config-file`` replaces the user configuration rather than adding to it."""
    result = invoke("config", "path")

    assert result.exit_code == 0
    assert str(tmp_path / "simdb.cfg") in result.output


def test_path_falls_back_to_the_user_configuration(runner, tmp_path):
    """Without ``--config-file`` the location comes from SIMDB_USER_CONFIG_PATH."""
    result = runner.invoke(cli, ["config", "path"])

    assert result.exit_code == 0
    assert str(tmp_path / "user-simdb.cfg") in result.output


@pytest.mark.parametrize("subcommand", ["get", "set", "delete"])
def test_missing_arguments_are_reported(invoke, subcommand):
    result = invoke("config", subcommand)

    assert result.exit_code == 2
    assert "Missing argument" in result.output
