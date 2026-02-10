import base64
import importlib
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from simdb.cli.manifest import Manifest
from simdb.config import Config
from simdb.database.models import Simulation
from simdb.remote.app import create_app

has_flask = importlib.util.find_spec("flask") is not None


TEST_PASSWORD = "test123"
CREDENTIALS = base64.b64encode(f"admin:{TEST_PASSWORD}".encode()).decode()
HEADERS = {"Authorization": f"Basic {CREDENTIALS}"}

SIMULATIONS = []
for _ in range(100):
    SIMULATIONS.append(Simulation(Manifest()))


@pytest.fixture(scope="session")
def client():
    config = Config()
    config.load()
    db_fd, db_file = tempfile.mkstemp()
    upload_dir = tempfile.mkdtemp()
    config.set_option("database.type", "sqlite")
    config.set_option("database.file", db_file)
    config.set_option("server.admin_password", TEST_PASSWORD)
    config.set_option("server.upload_folder", upload_dir)
    config.set_option("authentication.type", "None")
    config.set_option("server.copy_files", False)
    app = create_app(config=config, testing=True, debug=True)
    app.testing = True

    with app.test_client() as client:
        # with app.app_context():
        for sim in SIMULATIONS:
            app.db.insert_simulation(sim)

        app.db.session.commit()
        app.db.session.close()

        yield client

    os.close(db_fd)
    Path(app.simdb_config.get_option("database.file")).unlink()
    shutil.rmtree(upload_dir)


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_root(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert "endpoints" in rv.json
    assert len(rv.json["endpoints"]) > 0
    assert all(
        endpoint.startswith("http://localhost/v") for endpoint in rv.json["endpoints"]
    )


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_api_root(client):
    rv = client.get("/v1.2", headers=HEADERS)
    assert rv.status_code == 308


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations(client):
    rv = client.get("/v1.2/simulations", headers=HEADERS)
    assert rv.json["count"] == 100
    assert len(rv.json["results"]) == len(SIMULATIONS)
    assert rv.status_code == 200


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations(client):
    """Test POST endpoint for creating a new simulation."""
    # Create a new simulation data structure
    sim_uuid = uuid.uuid4()
    sim_uuid_hex = sim_uuid.hex
    input_uuid = uuid.uuid4()
    output_uuid = uuid.uuid4()

    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid_hex},
            "alias": "test-simulation",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [
                {
                    "uuid": {"_type": "uuid.UUID", "hex": input_uuid.hex},
                    "type": "FILE",
                    "uri": "file:///path/to/input/data.txt",
                    "checksum": "abc123def456",
                    "datetime": datetime.now(timezone.utc).isoformat(),
                    "usage": "input_data",
                    "purpose": "test input file",
                    "sensitivity": "public",
                    "access": "open",
                    "embargo": None,
                }
            ],
            "outputs": [
                {
                    "uuid": {"_type": "uuid.UUID", "hex": output_uuid.hex},
                    "type": "FILE",
                    "uri": "file:///path/to/output/results.txt",
                    "checksum": "xyz789abc012",
                    "datetime": datetime.now(timezone.utc).isoformat(),
                    "usage": "output_data",
                    "purpose": "test output file",
                    "sensitivity": "public",
                    "access": "open",
                    "embargo": None,
                }
            ],
            "metadata": [
                {"element": "machine", "value": "test-machine"},
                {"element": "code", "value": "test-code"},
                {"element": "description", "value": "Test simulation"},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    # POST the simulation
    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )

    # Verify the response
    if rv.status_code != 200:
        print(f"Response status: {rv.status_code}")
        print(f"Response data: {rv.data}")
        print(f"Response json: {rv.json if rv.is_json else 'Not JSON'}")

    assert "ingested" in rv.json
    assert rv.json["ingested"] == sim_uuid_hex

    # Verify the simulation was created by fetching it
    rv_get = client.get(f"/v1.2/simulation/{sim_uuid_hex}", headers=HEADERS)
    assert rv_get.status_code == 200
    assert rv_get.json["alias"] == "test-simulation"
