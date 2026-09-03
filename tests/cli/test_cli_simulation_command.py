from unittest import mock
from uuid import uuid1

import pytest
from click.testing import CliRunner
from utils import config_test_file

from simdb.cli.remote_api import FailedConnection, RemoteError
from simdb.cli.simdb import cli
from simdb.enums import IngestionStatus


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI")
def test_simulation_alias_command(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation"])
    assert result.exception is None


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI")
def test_simulation_delete_command(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation"])
    assert result.exception is None


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI")
def test_simulation_info_command(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation"])
    assert result.exception is None


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI")
def test_simulation_list_command(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation"])
    assert result.exception is None


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI")
def test_simulation_modify_command(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation"])
    assert result.exception is None


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI")
def test_simulation_new_command(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation"])
    assert result.exception is None


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI")
def test_simulation_push_command(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation"])
    assert result.exception is None


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI")
def test_simulation_query_command(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation"])
    assert result.exception is None


@mock.patch("simdb.database.get_local_db")
@mock.patch("simdb.cli.remote_api.RemoteAPI")
def test_simulation_validate_command(remote_api, get_local_db):
    config_file = config_test_file()
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation"])
    assert result.exception is None


@pytest.mark.parametrize(
    "subcommand, trailing_args",
    (
        ("push", ()),
        ("push_local", ()),
        ("pull", ("directory",)),
        ("data", ("ids_path",)),
        ("validate", ()),
    ),
)
@pytest.mark.parametrize(
    "options", (("--username", "bob"), ()), ids=("username", "none")
)
@pytest.mark.parametrize(
    "options_first", (True, False), ids=("options-first", "options-last")
)
@pytest.mark.parametrize("remote", (("test",), ()), ids=("test", "default"))
@mock.patch("simdb.cli.commands.simulation.RemoteAPI")
@mock.patch("simdb.cli.commands.simulation.get_local_db")
def test_optional_remote_argument(
    get_local_db, remote_api, remote, options_first, options, subcommand, trailing_args
):
    """REMOTE may be left out, wherever the options appear on the command line."""
    config_file = config_test_file()
    # push_local polls until the ingestion reaches a terminal state.
    remote_api.return_value.get_ingestion_status.return_value = (
        IngestionStatus.COMPLETED.value
    )
    arguments = (*remote, "sim_id", *trailing_args)
    argv = (*options, *arguments) if options_first else (*arguments, *options)

    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "simulation", subcommand, *argv]
    )

    assert remote_api.called, result.output
    used_remote, used_username = remote_api.call_args.args[:2]
    assert used_remote == (remote[0] if remote else "")
    assert used_username == ("bob" if options else None)


@mock.patch("simdb.cli.commands.simulation.RemoteAPI")
@mock.patch("simdb.cli.commands.simulation.get_local_db")
def test_simulation_push_local_command(get_local_db, remote_api):
    """push_local waits for the remote ingestion to complete."""
    config_file = config_test_file()
    remote_api.return_value.get_ingestion_status.return_value = (
        IngestionStatus.COMPLETED.value
    )
    simulation = get_local_db.return_value.get_simulation.return_value

    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "simulation", "push_local", "sim_id"]
    )

    assert result.exception is None, result.output
    remote_api.return_value.push_local_simulation.assert_called_once_with(
        simulation, add_watcher=False
    )
    assert f"Successfully pushed simulation {simulation.uuid}" in result.output


@pytest.mark.parametrize(
    "status", (IngestionStatus.COPY_FAILED, IngestionStatus.VALIDATION_FAILED)
)
@mock.patch("simdb.cli.commands.simulation.RemoteAPI")
@mock.patch("simdb.cli.commands.simulation.get_local_db")
def test_simulation_push_local_failed_ingestion(get_local_db, remote_api, status):
    """push_local fails when the remote ingestion does."""
    config_file = config_test_file()
    remote_api.return_value.get_ingestion_status.return_value = status.value

    runner = CliRunner()
    result = runner.invoke(
        cli, [f"--config-file={config_file}", "simulation", "push_local", "sim_id"]
    )

    assert result.exit_code != 0
    assert f"Simulation ingestion failed with status: {status.value}" in result.output


@mock.patch("simdb.cli.commands.simulation.RemoteAPI")
@mock.patch("simdb.cli.commands.simulation.get_local_db")
def test_simulation_push_local_timeout(get_local_db, remote_api):
    """push_local stops waiting once the --timeout has passed."""
    config_file = config_test_file()
    remote_api.return_value.get_ingestion_status.return_value = (
        IngestionStatus.COPYING.value
    )
    argv = ("push_local", "sim_id", "--timeout=0")

    runner = CliRunner()
    result = runner.invoke(cli, [f"--config-file={config_file}", "simulation", *argv])

    assert result.exit_code != 0
    assert "Timed out after 0s waiting for ingestion to complete" in result.output
    assert "last status: COPYING" in result.output


def _invoke_push_local(remote_api, *extra_args):
    config_file = config_test_file()
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            f"--config-file={config_file}",
            "simulation",
            "push_local",
            "sim_id",
            *extra_args,
        ],
    )


@mock.patch("simdb.cli.commands.simulation.time.sleep")
@mock.patch("simdb.cli.commands.simulation.RemoteAPI")
@mock.patch("simdb.cli.commands.simulation.get_local_db")
def test_simulation_push_local_reports_status_changes(get_local_db, remote_api, sleep):
    """push_local reports every ingestion status the remote goes through."""
    sim_uuid = uuid1()
    get_local_db.return_value.get_simulation.return_value.uuid = sim_uuid
    remote_api.return_value.get_ingestion_status.side_effect = [
        IngestionStatus.QUEUED.value,
        IngestionStatus.COPYING.value,
        IngestionStatus.COPYING.value,
        IngestionStatus.COMPLETED.value,
    ]

    result = _invoke_push_local(remote_api)

    assert result.exit_code == 0, result.output
    assert "QUEUED -> COPYING -> COMPLETED" in result.output
    assert f"Successfully pushed simulation {sim_uuid}" in result.output


@mock.patch("simdb.cli.commands.simulation.time.sleep")
@mock.patch("simdb.cli.commands.simulation.RemoteAPI")
@mock.patch("simdb.cli.commands.simulation.get_local_db")
def test_simulation_push_local_unknown_status(get_local_db, remote_api, sleep):
    """push_local does not wait for a status it cannot recognise."""
    remote_api.return_value.get_ingestion_status.return_value = "TELEPORTING"

    result = _invoke_push_local(remote_api)

    assert result.exit_code != 0
    assert "Remote reported an unknown ingestion status: TELEPORTING" in result.output


@mock.patch("simdb.cli.commands.simulation.time.sleep")
@mock.patch("simdb.cli.commands.simulation.RemoteAPI")
@mock.patch("simdb.cli.commands.simulation.get_local_db")
def test_simulation_push_local_transient_errors(get_local_db, remote_api, sleep):
    """The ingestion continues server-side, so a failed status check is not fatal."""
    remote_api.return_value.get_ingestion_status.side_effect = [
        FailedConnection("connection reset"),
        FailedConnection("connection reset"),
        IngestionStatus.COMPLETED.value,
    ]

    result = _invoke_push_local(remote_api)

    assert result.exit_code == 0, result.output
    assert "COMPLETED" in result.output


@mock.patch("simdb.cli.commands.simulation.time.sleep")
@mock.patch("simdb.cli.commands.simulation.RemoteAPI")
@mock.patch("simdb.cli.commands.simulation.get_local_db")
def test_simulation_push_local_persistent_errors(get_local_db, remote_api, sleep):
    """push_local gives up once the status check keeps failing."""
    remote_api.return_value.get_ingestion_status.side_effect = FailedConnection("down")

    result = _invoke_push_local(remote_api)

    assert result.exit_code != 0
    assert "Failed to check ingestion status 5 times in a row: down" in result.output


@mock.patch("simdb.cli.commands.simulation.time.sleep")
@mock.patch("simdb.cli.commands.simulation.RemoteAPI")
@mock.patch("simdb.cli.commands.simulation.get_local_db")
def test_simulation_push_local_rejected_status_check(get_local_db, remote_api, sleep):
    """A request the remote rejects will not start working when repeated."""
    remote_api.return_value.get_ingestion_status.side_effect = RemoteError(
        "Simulation not found"
    )

    result = _invoke_push_local(remote_api)

    assert result.exit_code != 0
    assert "Failed to check ingestion status: Simulation not found" in result.output
    assert remote_api.return_value.get_ingestion_status.call_count == 1
