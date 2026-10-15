from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from uuid import UUID

import pytest
import yaml
from conftest import (
    HEADERS,
    generate_simulation_data,
)

from simdb.checksum import calculate_checksum
from simdb.cli.manifest import Manifest
from simdb.config import Config
from simdb.database import DatabaseError
from simdb.database.models import Simulation
from simdb.enums import IngestionStatus
from simdb.remote.models import (
    FileData,
    SimulationPostResponse,
    SimulationStatusResponse,
)
from simdb.workers import tasks as simdb_tasks
from simdb.workers.celery import celery_app


@pytest.fixture(autouse=True)
def celery_eager_config():

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.result_backend = None
    yield


@pytest.fixture
def client_with_task_mock(client, monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    db_file.write_text("")
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    # The configuration the worker tasks see. Tests may add options to it.
    task_options = {
        "database.type": "sqlite",
        "database.file": str(db_file),
        "server.upload_folder": str(upload_dir),
        "partition.data": str(tmp_path / "partition"),
    }

    def mock_config():
        cfg = mock.MagicMock(spec=Config)
        cfg.get_option.side_effect = lambda key, **kwargs: task_options.get(
            key, kwargs.get("default")
        )
        cfg.get_string_option.side_effect = cfg.get_option.side_effect
        cfg.get_section.side_effect = lambda name, **kwargs: kwargs.get("default")
        cfg.sections.return_value = []
        cfg.load = mock.MagicMock()
        return cfg

    monkeypatch.setattr(simdb_tasks, "Config", mock_config)
    monkeypatch.setattr(simdb_tasks, "get_db", lambda cfg: client.application.db)
    monkeypatch.setattr(client.application.db, "close", lambda: None)

    client.task_options = task_options
    return client


@pytest.fixture
def auto_validate(client_with_task_mock, tmp_path):
    """Configure the server to validate uploads against a schema file.

    Returns a function that writes the given Cerberus schema and enables
    ``validation.auto_validate`` for both the API and the worker.
    """
    client = client_with_task_mock
    schema_file = tmp_path / "validation-schema.yaml"

    def configure(schema: dict, error_on_fail: bool = False):
        schema_file.write_text(yaml.safe_dump(schema))
        client.application.simdb_config.set_option("validation.path", str(schema_file))
        client.application.simdb_config.set_option("validation.auto_validate", True)
        client.application.simdb_config.set_option(
            "validation.error_on_fail", error_on_fail
        )
        client.task_options["validation.path"] = str(schema_file)
        client.task_options["validation.error_on_fail"] = error_on_fail

    return configure


def post_simulation_v13(client, simulation_data, headers=HEADERS):
    rv_post = client.post(
        "/v1.3/simulations",
        json=simulation_data.model_dump(mode="json"),
        headers=headers,
        content_type="application/json",
    )
    return rv_post


def get_simulation_status(client, simulation_uuid: UUID, headers=HEADERS):
    rv_get = client.get(
        f"/v1.3/simulation/status/{simulation_uuid.hex}", headers=headers
    )
    return rv_get


def generate_simulation_file(path) -> FileData:
    file_path = path / "partition/file.txt"
    file_path.parent.mkdir(exist_ok=True)
    file_path.write_text("test data")
    checksum = calculate_checksum(file_path)
    return FileData(
        type="FILE",
        uri="data:///file.txt",
        checksum=checksum,
        datetime=datetime.now(timezone.utc),
    )


def test_delete_simulation_during_ingestion_v13(client):
    """DELETE must be rejected with 409 while ingestion is in progress."""

    simulation = Simulation(Manifest())
    simulation.ingestion_status = IngestionStatus.QUEUED
    with client.application.app_context():
        client.application.db.insert_simulation(simulation)

    rv = client.delete(f"/v1.3/simulation/{simulation.uuid.hex}", headers=HEADERS)

    assert rv.status_code == 409
    assert "still being ingested" in rv.json["error"]

    with client.application.app_context():
        assert client.application.db.get_simulation(simulation.uuid.hex) is not None


def test_delete_simulation_after_ingestion_v13(client_with_task_mock, tmp_path):
    """DELETE succeeds once ingestion has completed."""
    client = client_with_task_mock
    simulation_data = generate_simulation_data(
        alias="test-delete-v13",
        inputs=[generate_simulation_file(tmp_path)],
        outputs=[generate_simulation_file(tmp_path)],
    )

    rv_post = post_simulation_v13(client, simulation_data)
    assert rv_post.status_code == 200
    sim_hex = SimulationPostResponse.model_validate(rv_post.json).ingested.hex

    rv = client.delete(f"/v1.3/simulation/{sim_hex}", headers=HEADERS)

    assert rv.status_code == 200
    assert UUID(rv.json["deleted"]["simulation"]).hex == sim_hex


def test_force_delete_stuck_simulation_v13(client):
    """A simulation stuck in a non-terminal ingestion state can be force-deleted."""
    simulation = Simulation(Manifest())
    simulation.ingestion_status = IngestionStatus.COPYING
    with client.application.app_context():
        client.application.db.insert_simulation(simulation)

    # Without force it is rejected because ingestion is not terminal.
    rv = client.delete(f"/v1.3/simulation/{simulation.uuid.hex}", headers=HEADERS)
    assert rv.status_code == 409

    # With force it succeeds, providing an escape hatch for stuck simulations.
    rv = client.delete(
        f"/v1.3/simulation/{simulation.uuid.hex}?force=true", headers=HEADERS
    )
    assert rv.status_code == 200
    assert UUID(rv.json["deleted"]["simulation"]).hex == simulation.uuid.hex


def test_post_simulations_v13(client_with_task_mock, tmp_path):
    """Test POST endpoint for creating a new simulation."""
    client = client_with_task_mock
    simulation_data = generate_simulation_data(
        alias="test-simulation-v13",
        inputs=[generate_simulation_file(tmp_path)],
        outputs=[generate_simulation_file(tmp_path)],
    )

    rv = post_simulation_v13(client, simulation_data)

    assert rv.status_code == 200

    result = SimulationPostResponse.model_validate(rv.json)
    assert result.ingested == simulation_data.simulation.uuid

    simulation = client.application.db.get_simulation(result.ingested.hex)
    assert simulation.ingestion_status == IngestionStatus.COMPLETED
    assert (
        Path(simulation.inputs[0].uri.path)
        == tmp_path / "uploads" / result.ingested.hex / "file.txt"
    )


@pytest.mark.xfail(
    reason="User.email is not set for admin without custom authenticators"
)
def test_post_simulations_with_watcher_v13(client_with_task_mock, tmp_path):
    """POST with add_watcher registers a watcher (parity with v1.2)."""
    client = client_with_task_mock
    simulation_data = generate_simulation_data(
        alias="test-watcher-v13",
        add_watcher=True,
        inputs=[generate_simulation_file(tmp_path)],
        outputs=[generate_simulation_file(tmp_path)],
    )

    rv = post_simulation_v13(client, simulation_data)
    assert rv.status_code == 200

    sim_hex = SimulationPostResponse.model_validate(rv.json).ingested.hex
    simulation = client.application.db.get_simulation(sim_hex)
    assert [watcher.email for watcher in simulation.watchers]


def test_post_simulations_v13_skips_validation_by_default(
    client_with_task_mock, tmp_path
):
    """Without auto_validate the ingestion chain never runs the validator."""
    client = client_with_task_mock
    simulation_data = generate_simulation_data(
        alias="test-no-validation-v13", inputs=[generate_simulation_file(tmp_path)]
    )

    with mock.patch("simdb.workers.tasks.validate_simulation") as validate:
        rv = post_simulation_v13(client, simulation_data)

    assert rv.status_code == 200
    validate.assert_not_called()
    sim_hex = SimulationPostResponse.model_validate(rv.json).ingested.hex
    simulation = client.application.db.get_simulation(sim_hex)
    assert simulation.ingestion_status == IngestionStatus.COMPLETED
    assert simulation.status is None


def test_post_simulations_v13_validates_after_copying(
    client_with_task_mock, auto_validate, tmp_path
):
    """With auto_validate the worker validates the simulation and records it."""
    client = client_with_task_mock
    auto_validate({"description": {"type": "string"}})
    simulation_data = generate_simulation_data(
        alias="test-validated-v13", inputs=[generate_simulation_file(tmp_path)]
    )

    rv = post_simulation_v13(client, simulation_data)

    assert rv.status_code == 200
    sim_hex = SimulationPostResponse.model_validate(rv.json).ingested.hex
    simulation = client.application.db.get_simulation(sim_hex)
    assert simulation.ingestion_status == IngestionStatus.COMPLETED
    assert simulation.status == Simulation.Status.PASSED
    status = SimulationStatusResponse.model_validate(
        get_simulation_status(client, simulation.uuid).json
    )
    assert status.error is None


def test_post_simulations_v13_runs_the_file_validator(
    client_with_task_mock, auto_validate, tmp_path
):
    """The configured file validator sees the ingested output files."""
    client = client_with_task_mock
    auto_validate({})
    client.task_options["file_validation.type"] = "ids_validator"
    simulation_data = generate_simulation_data(
        alias="test-file-validated-v13", outputs=[generate_simulation_file(tmp_path)]
    )
    validator = mock.MagicMock()

    with mock.patch(
        "simdb.validation.simulation.find_file_validator",
        return_value=(validator, "options"),
    ):
        rv = post_simulation_v13(client, simulation_data)

    assert rv.status_code == 200
    sim_hex = SimulationPostResponse.model_validate(rv.json).ingested.hex
    simulation = client.application.db.get_simulation(sim_hex)
    assert simulation.ingestion_status == IngestionStatus.COMPLETED
    (uri, options), _ = validator.validate_uri.call_args
    assert uri == simulation.outputs[0].uri
    assert options == "options"


def test_post_simulations_v13_ingests_a_failed_simulation_by_default(
    client_with_task_mock, auto_validate, tmp_path
):
    """Without error_on_fail a failed validation only marks the simulation."""
    client = client_with_task_mock
    auto_validate({"machine": {"type": "string", "required": True}})
    simulation_data = generate_simulation_data(
        alias="test-failed-validation-v13", inputs=[generate_simulation_file(tmp_path)]
    )

    rv = post_simulation_v13(client, simulation_data)

    assert rv.status_code == 200
    sim_hex = SimulationPostResponse.model_validate(rv.json).ingested.hex
    simulation = client.application.db.get_simulation(sim_hex)
    assert simulation.ingestion_status == IngestionStatus.COMPLETED
    assert simulation.status == Simulation.Status.FAILED
    status = SimulationStatusResponse.model_validate(
        get_simulation_status(client, simulation.uuid).json
    )
    assert status.status == IngestionStatus.COMPLETED
    assert "machine" in status.error


def test_post_simulations_v13_error_on_fail_stops_the_ingestion(
    client_with_task_mock, auto_validate, tmp_path
):
    """With error_on_fail a failed validation ends the ingestion."""
    client = client_with_task_mock
    auto_validate({"machine": {"type": "string", "required": True}}, error_on_fail=True)
    simulation_data = generate_simulation_data(
        alias="test-rejected-validation-v13",
        inputs=[generate_simulation_file(tmp_path)],
    )

    rv = post_simulation_v13(client, simulation_data)

    # The tasks run in-process here, so the failed validation is reported in
    # the response as v1.2 does. With a worker the request returns 200 and the
    # failure surfaces through the status endpoint checked below.
    assert rv.status_code == 400
    assert "error_on_fail=True" in rv.json["error"]
    assert "machine" in rv.json["error"]
    sim_hex = simulation_data.simulation.uuid.hex
    simulation = client.application.db.get_simulation(sim_hex)
    assert simulation.ingestion_status == IngestionStatus.VALIDATION_FAILED
    assert simulation.status == Simulation.Status.FAILED
    status = SimulationStatusResponse.model_validate(
        get_simulation_status(client, simulation.uuid).json
    )
    assert status.status == IngestionStatus.VALIDATION_FAILED
    assert "machine" in status.error

    # A failed ingestion is terminal, so the simulation can be cleaned up.
    rv = client.delete(f"/v1.3/simulation/{sim_hex}", headers=HEADERS)
    assert rv.status_code == 200


def test_post_simulations_v13_rejects_error_on_fail_without_auto_validate(
    client_with_task_mock, tmp_path
):
    client = client_with_task_mock
    client.application.simdb_config.set_option("validation.error_on_fail", True)
    simulation_data = generate_simulation_data(
        alias="test-misconfigured-v13", inputs=[generate_simulation_file(tmp_path)]
    )

    rv = post_simulation_v13(client, simulation_data)

    assert rv.status_code == 400
    assert "error_on_fail=True without auto_validate=True" in rv.json["error"]
    with pytest.raises(DatabaseError):
        client.application.db.get_simulation(simulation_data.simulation.uuid.hex)


def test_validate_simulation_reports_a_misconfigured_file_validator(
    client_with_task_mock, auto_validate
):
    """A file validator the server does not know is a server error, not a pass."""
    client = client_with_task_mock
    auto_validate({})
    client.application.simdb_config.set_option("file_validation.type", "nope")
    simulation = Simulation(Manifest())
    with client.application.app_context():
        client.application.db.insert_simulation(simulation)

    rv = client.post(f"/v1.3/validate/{simulation.uuid.hex}", headers=HEADERS)

    assert rv.status_code == 500
    assert "nope" in rv.json["error"]
