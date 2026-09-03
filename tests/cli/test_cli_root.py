"""Tests for the top level ``simdb`` group in :mod:`simdb.cli.simdb`."""

from unittest import mock

import pytest
from cli_helpers import make_simulation

from simdb import __version__
from simdb.cli import simdb as simdb_cli
from simdb.cli.simdb import cli


def test_version_option_reports_the_package_version(runner):
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_every_command(runner):
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    commands = ("alias", "config", "manifest", "provenance", "remote", "simulation")
    for command in commands:
        assert command in result.output


def test_commands_are_listed_in_alphabetical_order():
    listed = cli.list_commands(None)

    assert listed == sorted(listed)
    assert "sim" in listed


def test_sim_is_an_alias_for_simulation(runner):
    result = runner.invoke(cli, ["--help"])

    assert "Alias for simulation." in result.output
    assert cli.get_command(None, "sim") is not None


def test_the_alias_reaches_the_same_command(invoke, local_db):
    local_db.list_simulations.return_value = []

    assert invoke("sim", "list").exit_code == 0
    assert local_db.list_simulations.called


def test_unknown_commands_are_rejected(runner):
    result = runner.invoke(cli, ["nonsense"])

    assert result.exit_code == 2


def test_hidden_dump_help_prints_help_for_every_subcommand(runner):
    result = runner.invoke(cli, ["dump-help"])

    assert result.exit_code == 0
    # Both a group and one of its sub-commands are documented.
    assert "Manage ingested simulations." in result.output
    assert "List ingested simulations." in result.output
    assert "Query/update application configuration." in result.output


def test_dump_help_is_hidden_from_the_command_list(runner):
    assert "dump-help" not in runner.invoke(cli, ["--help"]).output


def test_config_file_option_is_loaded(invoke):
    """The remote declared in the config file is visible to the commands."""
    result = invoke("remote", "config", "list")

    assert result.exit_code == 0
    assert "test: http://0.0.0.0:5000/" in result.output
    assert "(default)" in result.output


def test_a_missing_config_file_is_reported(runner, tmp_path):
    result = runner.invoke(
        cli, [f"--config-file={tmp_path / 'nope.cfg'}", "config", "path"]
    )

    assert result.exit_code == 2
    assert "No such file or directory" in result.output


def test_verbose_flag_reaches_the_commands(invoke, local_db):
    """``--verbose`` is what turns on the extra columns of ``simulation list``."""
    local_db.list_simulations.return_value = [make_simulation("sim")]

    assert "status" not in invoke("simulation", "list").output
    assert "status" in invoke("--verbose", "simulation", "list").output


class TestMain:
    """``main`` is the console-script entry point and the CLI's last error handler."""

    def test_successful_runs_do_not_raise(self):
        with mock.patch.object(simdb_cli, "cli") as command:
            simdb_cli.main()

        assert command.called

    def test_errors_are_reported_and_exit_non_zero(self, capsys):
        with mock.patch.object(
            simdb_cli, "cli", side_effect=RuntimeError("boom")
        ), pytest.raises(SystemExit) as exit_info:
            simdb_cli.main()

        assert exit_info.value.code == 1
        assert "Error: boom" in capsys.readouterr().err

    def test_debug_mode_re_raises_for_a_traceback(self, monkeypatch):
        monkeypatch.setattr(simdb_cli, "g_debug", True)

        with mock.patch.object(
            simdb_cli, "cli", side_effect=RuntimeError("boom")
        ), pytest.raises(RuntimeError, match="boom"):
            simdb_cli.main()

    def test_the_debug_flag_switches_debug_mode_on(self, invoke):
        """``-d`` is what makes :func:`main` re-raise instead of printing.

        ``--help`` is eager and exits before the group callback runs, so the
        flag only takes effect when a command is actually invoked.
        """
        invoke("-d", "config", "path")
        assert simdb_cli.g_debug is True

        # Leave the module global as the other tests expect to find it.
        invoke("config", "path")
        assert simdb_cli.g_debug is False
