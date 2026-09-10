"""Tests for ``simdb simulation``.

The local database and the remote are stubbed; what is exercised here is the
command layer itself: argument parsing, the branches each command takes, the
calls it makes, and what it reports back to the user.
"""

from unittest import mock

import pytest
from cli_helpers import make_simulation

from simdb.cli.remote_api import RemoteError
from simdb.database import DatabaseError
from simdb.remote.models import ImasDataResponse, QuantityData
from simdb.validation import ValidationError


@pytest.fixture
def remote_api():
    """Replace the ``RemoteAPI`` the simulation commands construct."""
    with mock.patch("simdb.cli.commands.simulation.RemoteAPI") as remote_api_cls:
        yield remote_api_cls.return_value


# ---------------------------------------------------------------------------
# simulation list
# ---------------------------------------------------------------------------


def test_list_prints_every_alias(invoke, local_db):
    local_db.list_simulations.return_value = [
        make_simulation("first"),
        make_simulation("second"),
    ]

    result = invoke("simulation", "list")

    assert result.exit_code == 0
    assert "first" in result.output
    assert "second" in result.output
    assert local_db.list_simulations.call_args.kwargs == {
        "meta_keys": (),
        "limit": 100,
    }


def test_list_reports_an_empty_database(invoke, local_db):
    local_db.list_simulations.return_value = []

    result = invoke("simulation", "list")

    assert result.exit_code == 0
    assert "No simulations found" in result.output


def test_list_shows_uuid_and_metadata_columns_on_request(invoke, local_db):
    local_db.list_simulations.return_value = [
        make_simulation("first", uuid="abcd1234", meta={"pulse": 134173})
    ]

    result = invoke("simulation", "list", "--uuid", "--meta-data=pulse")

    assert result.exit_code == 0
    assert "abcd1234" in result.output
    assert "134173" in result.output
    assert local_db.list_simulations.call_args.kwargs["meta_keys"] == ("pulse",)


def test_list_passes_the_requested_limit(invoke, local_db):
    local_db.list_simulations.return_value = []

    assert invoke("simulation", "list", "--limit=5").exit_code == 0

    assert local_db.list_simulations.call_args.kwargs["limit"] == 5


def test_list_rejects_a_negative_limit(invoke, local_db):
    result = invoke("simulation", "list", "--limit=-1")

    assert result.exit_code == 2
    assert "must be non-negative" in result.output
    assert not local_db.list_simulations.called


# ---------------------------------------------------------------------------
# simulation modify
# ---------------------------------------------------------------------------


def test_modify_sets_a_new_alias(invoke, local_db):
    simulation = make_simulation("old")
    local_db.get_simulation.return_value = simulation

    result = invoke("simulation", "modify", "old", "--alias=new")

    assert result.exit_code == 0
    assert "alias updated" in result.output
    assert simulation.alias == "new"
    assert local_db.session.commit.called


def test_modify_sets_metadata(invoke, local_db):
    simulation = make_simulation("sim")
    local_db.get_simulation.return_value = simulation

    result = invoke("simulation", "modify", "sim", "--set-meta=pulse=134173")

    assert result.exit_code == 0
    assert "metadata updated" in result.output
    simulation.set_meta.assert_called_once_with("pulse", "134173")
    assert local_db.session.commit.called


def test_modify_rejects_metadata_without_a_value(invoke, local_db):
    result = invoke("simulation", "modify", "sim", "--set-meta=pulse")

    assert result.exit_code == 2
    assert "must be of form NAME=VALUE" in result.output
    assert not local_db.session.commit.called


def test_modify_deletes_metadata(invoke, local_db):
    simulation = make_simulation("sim")
    local_db.get_simulation.return_value = simulation

    result = invoke("simulation", "modify", "sim", "--del-meta=pulse")

    assert result.exit_code == 0
    assert "metadata deleted" in result.output
    simulation.remove_meta.assert_called_once_with("pulse")


def test_modify_without_options_changes_nothing(invoke, local_db):
    result = invoke("simulation", "modify", "sim")

    assert result.exit_code == 0
    assert "nothing to do" in result.output
    assert not local_db.get_simulation.called


# ---------------------------------------------------------------------------
# simulation delete
# ---------------------------------------------------------------------------


def test_delete_removes_a_single_simulation(invoke, local_db):
    simulation = make_simulation("sim")
    simulation.uuid = mock.Mock(hex="abcd1234")
    local_db.delete_simulation.return_value = simulation

    result = invoke("simulation", "delete", "sim")

    assert result.exit_code == 0
    assert "abcd1234 deleted" in result.output
    local_db.delete_simulation.assert_called_once_with("sim")


def test_delete_requires_a_simulation_or_all(invoke, local_db):
    result = invoke("simulation", "delete")

    assert result.exit_code != 0
    assert "Either SIM_ID or --all must be provided" in result.output


def test_delete_all_removes_the_database_file_once_confirmed(
    invoke, local_db, tmp_path
):
    database_file = tmp_path / "sim.db"
    database_file.write_text("not really a database")

    with mock.patch(
        "simdb.cli.commands.simulation.Confirm.ask", return_value=True
    ) as ask:
        result = invoke("simulation", "delete", "--all")

    assert result.exit_code == 0
    assert "Local database reset." in result.output
    assert ask.called
    assert not database_file.exists()


def test_delete_all_keeps_the_database_when_not_confirmed(invoke, local_db, tmp_path):
    database_file = tmp_path / "sim.db"
    database_file.write_text("not really a database")

    with mock.patch("simdb.cli.commands.simulation.Confirm.ask", return_value=False):
        result = invoke("simulation", "delete", "--all")

    # Declining the reset falls through to the single-simulation path, which has
    # no SIM_ID to work with.
    assert result.exit_code != 0
    assert "Either SIM_ID or --all must be provided" in result.output
    assert database_file.exists()


# ---------------------------------------------------------------------------
# simulation info
# ---------------------------------------------------------------------------


def test_info_prints_the_simulation(invoke, local_db):
    local_db.get_simulation.return_value = "simulation description"

    result = invoke("simulation", "info", "sim")

    assert result.exit_code == 0
    assert "simulation description" in result.output
    local_db.get_simulation.assert_called_once_with("sim")


def test_info_fails_when_the_simulation_is_unknown(invoke, local_db):
    local_db.get_simulation.return_value = None

    result = invoke("simulation", "info", "sim")

    assert result.exit_code != 0
    assert isinstance(result.exception, KeyError)


# ---------------------------------------------------------------------------
# simulation ingest
# ---------------------------------------------------------------------------


def test_ingest_stores_the_manifest_and_reports_the_alias(
    invoke, local_db, manifest_file
):
    result = invoke("simulation", "ingest", str(manifest_file))

    assert result.exit_code == 0
    assert "ALIAS: simulation-alias" in result.output
    assert local_db.insert_simulation.called
    (simulation,) = local_db.insert_simulation.call_args.args
    assert simulation.alias == "simulation-alias"
    assert len(simulation.inputs) == 1
    assert len(simulation.outputs) == 1


def test_ingest_alias_option_overrides_the_manifest(invoke, local_db, manifest_file):
    result = invoke("simulation", "ingest", str(manifest_file), "--alias=override")

    assert result.exit_code == 0
    assert "ALIAS: override" in result.output
    (simulation,) = local_db.insert_simulation.call_args.args
    assert simulation.alias == "override"


def test_ingest_rejects_an_alias_with_reserved_characters(
    invoke, local_db, manifest_file
):
    """The manifest refuses the alias before the simulation is built.

    ``simulation_ingest`` also has a "warning: alias contains reserved
    characters" branch, but ``Manifest.validate_alias`` applies the identical
    ``urllib.parse.quote`` check to both the manifest alias and the ``--alias``
    override, so that branch cannot be reached.
    """
    result = invoke("simulation", "ingest", str(manifest_file), "--alias=with space")

    assert result.exit_code != 0
    assert "illegal characters in alias" in str(result.exception)
    assert not local_db.insert_simulation.called


def test_ingest_requires_an_existing_manifest(invoke, local_db, tmp_path):
    result = invoke("simulation", "ingest", str(tmp_path / "missing.yaml"))

    assert result.exit_code == 2
    assert not local_db.insert_simulation.called


# ---------------------------------------------------------------------------
# simulation query
# ---------------------------------------------------------------------------


def test_query_parses_constraints_and_prints_matches(invoke, local_db):
    local_db.query_meta.return_value = [make_simulation("match")]

    result = invoke("simulation", "query", "pulse=gt:1000", "run=0")

    assert result.exit_code == 0
    assert "match" in result.output
    (constraints,) = local_db.query_meta.call_args.args
    assert [(name, value) for name, value, _ in constraints] == [
        ("pulse", "1000"),
        ("run", "0"),
    ]


def test_query_requires_a_constraint(invoke, local_db):
    result = invoke("simulation", "query")

    assert result.exit_code != 0
    assert "At least one constraint must be provided" in result.output
    assert not local_db.query_meta.called


def test_query_rejects_a_constraint_without_a_value(invoke, local_db):
    result = invoke("simulation", "query", "pulse")

    assert result.exit_code != 0
    assert "Invalid constraint pulse" in result.output
    assert not local_db.query_meta.called


# ---------------------------------------------------------------------------
# simulation push
# ---------------------------------------------------------------------------


def test_push_validates_and_uploads_the_simulation(invoke, local_db, remote_api):
    simulation = make_simulation("sim")
    local_db.get_simulation.return_value = simulation
    remote_api.get_validation_schemas.return_value = []

    result = invoke("simulation", "push", "sim")

    assert result.exit_code == 0
    assert "Successfully pushed simulation" in result.output
    assert remote_api.push_simulation.call_args.args == (simulation,)
    assert remote_api.push_simulation.call_args.kwargs["add_watcher"] is False


def test_push_records_the_replaced_simulation(invoke, local_db, remote_api):
    simulation = make_simulation("sim")
    local_db.get_simulation.return_value = simulation
    remote_api.get_validation_schemas.return_value = []

    result = invoke("simulation", "push", "sim", "--replaces=older")

    assert result.exit_code == 0
    simulation.set_meta.assert_called_once_with("replaces", "older")


def test_push_adds_a_watcher_on_request(invoke, local_db, remote_api):
    local_db.get_simulation.return_value = make_simulation("sim")
    remote_api.get_validation_schemas.return_value = []

    result = invoke("simulation", "push", "sim", "--add-watcher")

    assert result.exit_code == 0
    assert remote_api.push_simulation.call_args.kwargs["add_watcher"] is True


def test_push_fails_when_the_simulation_is_unknown(invoke, local_db, remote_api):
    local_db.get_simulation.return_value = None

    result = invoke("simulation", "push", "sim")

    assert result.exit_code != 0
    assert "Failed to find simulation: sim" in result.output
    assert not remote_api.push_simulation.called


def test_push_reports_validation_failures_without_uploading(
    invoke, local_db, remote_api
):
    local_db.get_simulation.return_value = make_simulation("sim")
    remote_api.get_validation_schemas.return_value = [{"alias": {"type": "string"}}]

    with mock.patch("simdb.cli.commands.simulation.Validator") as validator:
        validator.return_value.validate.side_effect = ValidationError("bad metadata")
        result = invoke("simulation", "push", "sim")

    assert result.exit_code != 0
    assert "Simulation does not validate: bad metadata" in result.output
    assert not remote_api.push_simulation.called


# ---------------------------------------------------------------------------
# simulation pull
# ---------------------------------------------------------------------------


def test_pull_stores_the_simulation_locally(invoke, local_db, remote_api, tmp_path):
    local_db.get_simulation.side_effect = DatabaseError("not found")
    pulled = make_simulation("pulled")
    remote_api.pull_simulation.return_value = pulled

    result = invoke("simulation", "pull", "sim", str(tmp_path / "out"))

    assert result.exit_code == 0
    assert "Successfully pulled simulation" in result.output
    local_db.insert_simulation.assert_called_once_with(pulled)


def test_pull_refuses_to_overwrite_an_existing_simulation(
    invoke, local_db, remote_api, tmp_path
):
    local_db.get_simulation.return_value = make_simulation("sim")

    result = invoke("simulation", "pull", "sim", str(tmp_path / "out"))

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert not remote_api.pull_simulation.called
    assert not local_db.insert_simulation.called


def test_pull_reports_remote_errors(invoke, local_db, remote_api, tmp_path):
    local_db.get_simulation.side_effect = DatabaseError("not found")
    remote_api.pull_simulation.side_effect = RemoteError("remote is down")

    result = invoke("simulation", "pull", "sim", str(tmp_path / "out"))

    assert result.exit_code != 0
    assert "remote is down" in result.output
    assert not local_db.insert_simulation.called


# ---------------------------------------------------------------------------
# simulation data
# ---------------------------------------------------------------------------


def _data_response(field_data, coordinates=()):
    return ImasDataResponse(
        simulation="abcd1234",
        path="core_profiles/profiles_1d[0]/grid/rho_tor_norm",
        occurrence=0,
        field=QuantityData(name="grid/rho_tor_norm", units="-", data=field_data),
        coordinates=list(coordinates),
    )


def test_data_plots_a_one_dimensional_field(invoke, remote_api):
    remote_api.get_simulation_data.return_value = _data_response([0.0, 0.5, 1.0])

    result = invoke("simulation", "data", "sim", "core_profiles/grid/rho_tor_norm")

    assert result.exit_code == 0
    assert "abcd1234" in result.output
    assert "occurrence 0" in result.output
    assert remote_api.get_simulation_data.call_args.args == (
        "sim",
        "core_profiles/grid/rho_tor_norm",
    )
    assert remote_api.get_simulation_data.call_args.kwargs == {"dd_version": None}


def test_data_forwards_the_requested_dd_version(invoke, remote_api):
    remote_api.get_simulation_data.return_value = _data_response(1.5)

    result = invoke(
        "simulation", "data", "sim", "core_profiles/time", "--dd-version=4.1.1"
    )

    assert result.exit_code == 0
    assert remote_api.get_simulation_data.call_args.kwargs == {"dd_version": "4.1.1"}


def test_data_reports_remote_failures_as_a_clean_error(invoke, remote_api):
    remote_api.get_simulation_data.side_effect = RemoteError("no such field")

    result = invoke("simulation", "data", "sim", "core_profiles/nope")

    assert result.exit_code != 0
    assert "no such field" in result.output


# ---------------------------------------------------------------------------
# simulation validate
# ---------------------------------------------------------------------------


def test_validate_checks_metadata_and_file_checksums(invoke, local_db, remote_api):
    file = mock.Mock(uri="file:///data", checksum="abc")
    file.generate_checksum.return_value = "abc"
    simulation = make_simulation("sim")
    simulation.inputs = [file]
    simulation.outputs = []
    local_db.get_simulation.return_value = simulation
    remote_api.get_validation_schemas.return_value = []

    result = invoke("simulation", "validate", "sim")

    assert result.exit_code == 0
    assert "validation successful" in result.output


def test_validate_fails_on_a_checksum_mismatch(invoke, local_db, remote_api):
    file = mock.Mock(uri="file:///data", checksum="abc")
    file.generate_checksum.return_value = "different"
    simulation = make_simulation("sim")
    simulation.inputs = [file]
    simulation.outputs = []
    local_db.get_simulation.return_value = simulation
    remote_api.get_validation_schemas.return_value = []

    result = invoke("simulation", "validate", "sim")

    assert result.exit_code != 0
    assert isinstance(result.exception, ValidationError)
    assert "file:///data" in str(result.exception)
