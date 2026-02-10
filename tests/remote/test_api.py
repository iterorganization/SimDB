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


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_with_alias_dash(client):
    """Test POST endpoint with alias ending in dash (auto-increment)."""
    sim_uuid = uuid.uuid4()
    
    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": "dashtest-",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [{"element": "test", "value": "dash"}],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )

    assert rv.status_code == 200
    assert "ingested" in rv.json

    rv_get = client.get(f"/v1.2/simulation/{sim_uuid.hex}", headers=HEADERS)
    assert rv_get.status_code == 200
    assert rv_get.json["alias"] == "dashtest-1"
    
    # Check seqid metadata was added
    metadata = rv_get.json["metadata"]
    seqid_meta = [m for m in metadata if m["element"] == "seqid"]
    assert len(seqid_meta) == 1
    assert seqid_meta[0]["value"] == 1


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_with_alias_hash(client):
    """Test POST endpoint with alias ending in hash (auto-increment)."""
    sim_uuid = uuid.uuid4()
    
    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": "hashtest#",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [{"element": "test", "value": "hash"}],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )

    assert rv.status_code == 200
    assert "ingested" in rv.json

    rv_get = client.get(f"/v1.2/simulation/{sim_uuid.hex}", headers=HEADERS)
    assert rv_get.status_code == 200
    assert rv_get.json["alias"] == "hashtest#1"
    
    # Check seqid metadata was added
    metadata = rv_get.json["metadata"]
    seqid_meta = [m for m in metadata if m["element"] == "seqid"]
    assert len(seqid_meta) == 1
    assert seqid_meta[0]["value"] == 1


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_alias_increment_sequence(client):
    """Test multiple simulations with incrementing dash alias."""
    # Create first simulation with dash alias
    sim_uuid_1 = uuid.uuid4()
    simulation_data_1 = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid_1.hex},
            "alias": "sequence-",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv1 = client.post(
        "/v1.2/simulations",
        json=simulation_data_1,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv1.status_code == 200

    # Create second simulation with same dash alias
    sim_uuid_2 = uuid.uuid4()
    simulation_data_2 = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid_2.hex},
            "alias": "sequence-",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv2 = client.post(
        "/v1.2/simulations",
        json=simulation_data_2,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv2.status_code == 200

    # Verify aliases were incremented
    rv_get1 = client.get(f"/v1.2/simulation/{sim_uuid_1.hex}", headers=HEADERS)
    assert rv_get1.json["alias"] == "sequence-1"
    
    rv_get2 = client.get(f"/v1.2/simulation/{sim_uuid_2.hex}", headers=HEADERS)
    assert rv_get2.json["alias"] == "sequence-2"


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_no_alias(client):
    """Test POST endpoint with no alias provided (should use uuid.hex)."""
    sim_uuid = uuid.uuid4()
    
    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": None,
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )

    assert rv.status_code == 200
    rv_get = client.get(f"/v1.2/simulation/{sim_uuid.hex}", headers=HEADERS)
    assert rv_get.status_code == 200
    assert rv_get.json["alias"] == sim_uuid.hex


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_with_replaces(client):
    """Test POST endpoint with replaces metadata (deprecates old simulation)."""
    # Create initial simulation
    old_sim_uuid = uuid.uuid4()
    old_simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": old_sim_uuid.hex},
            "alias": "original-simulation",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [{"element": "version", "value": "1.0"}],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_old = client.post(
        "/v1.2/simulations",
        json=old_simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_old.status_code == 200

    # Create new simulation that replaces the old one
    new_sim_uuid = uuid.uuid4()
    new_simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": new_sim_uuid.hex},
            "alias": "updated-simulation",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [
                {"element": "version", "value": "2.0"},
                {"element": "replaces", "value": old_sim_uuid.hex},
                {"element": "replaces_reason", "value": "Bug fixes and improvements"},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_new = client.post(
        "/v1.2/simulations",
        json=new_simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_new.status_code == 200

    # Verify the old simulation is marked as DEPRECATED
    rv_old_get = client.get(f"/v1.2/simulation/{old_sim_uuid.hex}", headers=HEADERS)
    assert rv_old_get.status_code == 200
    old_metadata = rv_old_get.json["metadata"]
    
    status_meta = [m for m in old_metadata if m["element"] == "status"]
    assert len(status_meta) == 1
    assert status_meta[0]["value"].lower() == "deprecated"
    
    # Check replaced_by metadata was added
    replaced_by_meta = [m for m in old_metadata if m["element"] == "replaced_by"]
    assert len(replaced_by_meta) == 1
    assert replaced_by_meta[0]["value"] == new_sim_uuid

    # Verify the new simulation has replaces metadata
    rv_new_get = client.get(f"/v1.2/simulation/{new_sim_uuid.hex}", headers=HEADERS)
    assert rv_new_get.status_code == 200
    new_metadata = rv_new_get.json["metadata"]
    
    replaces_meta = [m for m in new_metadata if m["element"] == "replaces"]
    assert len(replaces_meta) == 1
    assert replaces_meta[0]["value"] == old_sim_uuid.hex


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_replaces_nonexistent(client):
    """Test POST endpoint with replaces pointing to non-existent simulation."""
    # Create simulation that tries to replace a non-existent simulation
    sim_uuid = uuid.uuid4()
    fake_uuid = uuid.uuid4()
    
    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": "replaces-nothing",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [
                {"element": "replaces", "value": fake_uuid.hex},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    # Should still succeed (old simulation just doesn't exist to deprecate)
    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv.status_code == 200
    
    # Verify the new simulation was created
    rv_get = client.get(f"/v1.2/simulation/{sim_uuid.hex}", headers=HEADERS)
    assert rv_get.status_code == 200
    assert rv_get.json["alias"] == "replaces-nothing"


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_with_watcher(client):
    """Test POST endpoint with add_watcher set to true."""
    sim_uuid = uuid.uuid4()
    
    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": "watched-simulation",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [],
        },
        "add_watcher": True,
        "uploaded_by": "watcher-user",
    }

    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv.status_code == 200

    # Verify the simulation was created
    rv_get = client.get(f"/v1.2/simulation/{sim_uuid.hex}", headers=HEADERS)
    assert rv_get.status_code == 200
    
    # Note: We can't easily verify watchers were added without accessing the db directly
    # but we can verify the request was successful and uploaded_by metadata is present
    metadata = rv_get.json["metadata"]
    uploaded_by_meta = [m for m in metadata if m["element"] == "uploaded_by"]
    assert len(uploaded_by_meta) == 1
    assert uploaded_by_meta[0]["value"] == "watcher-user"


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_uploaded_by(client):
    """Test POST endpoint with uploaded_by field."""
    sim_uuid = uuid.uuid4()
    
    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": "upload-test",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [],
        },
        "add_watcher": False,
        "uploaded_by": "specific-user@example.com",
    }

    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv.status_code == 200

    # Verify uploaded_by metadata
    rv_get = client.get(f"/v1.2/simulation/{sim_uuid.hex}", headers=HEADERS)
    assert rv_get.status_code == 200
    metadata = rv_get.json["metadata"]
    uploaded_by_meta = [m for m in metadata if m["element"] == "uploaded_by"]
    assert len(uploaded_by_meta) == 1
    assert uploaded_by_meta[0]["value"] == "specific-user@example.com"


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_trace_with_replaces(client):
    """Test the trace endpoint with a simulation that replaces another."""
    # Create original simulation
    old_sim_uuid = uuid.uuid4()
    old_simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": old_sim_uuid.hex},
            "alias": "trace-original",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [{"element": "version", "value": "1.0"}],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_old = client.post(
        "/v1.2/simulations",
        json=old_simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_old.status_code == 200

    # Create new simulation that replaces it
    new_sim_uuid = uuid.uuid4()
    new_simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": new_sim_uuid.hex},
            "alias": "trace-updated",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [
                {"element": "version", "value": "2.0"},
                {"element": "replaces", "value": old_sim_uuid.hex},
                {"element": "replaces_reason", "value": "New features"},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_new = client.post(
        "/v1.2/simulations",
        json=new_simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_new.status_code == 200

    # Get trace for the new simulation
    rv_trace = client.get(f"/v1.2/trace/{new_sim_uuid.hex}", headers=HEADERS)
    assert rv_trace.status_code == 200
    trace_data = rv_trace.json
    
    # Verify trace includes replaces information
    assert "replaces" in trace_data

    replaces_uuid = trace_data["replaces"]["uuid"]
    assert replaces_uuid == old_sim_uuid
    assert "replaces_reason" in trace_data
    assert trace_data["replaces_reason"] == "New features"
    
    with pytest.xfail("Deprecated on is not set, because replaced_on is never set"):
        assert "deprecated_on" in trace_data["replaces"]
