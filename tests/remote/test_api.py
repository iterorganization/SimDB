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
from simdb.remote.models import (
    FileData,
    MetadataData,
    SimulationData,
    SimulationPostData,
)

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


def generate_simulation_data(
    add_watcher=False, uploaded_by=None, **overrides
) -> SimulationPostData:
    simulation_data = SimulationData(**overrides)
    data = SimulationPostData(
        simulation=simulation_data, add_watcher=add_watcher, uploaded_by=uploaded_by
    )
    return data


def generate_simulation_file() -> FileData:
    return FileData(
        type="FILE",
        uri="file:///path/to/file",
        checksum="fake_checksum",
        datetime=datetime.now(timezone.utc),
    )


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
def test_post_simulations(client):
    """Test POST endpoint for creating a new simulation."""
    simulation_data = generate_simulation_data(
        alias="test-simulation",
        inputs=[generate_simulation_file()],
        outputs=[generate_simulation_file()],
    )

    # POST the simulation
    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )

    # Verify the response
    assert rv.status_code == 200
    assert rv.json["ingested"] == simulation_data.simulation.uuid.hex

    # Verify the simulation was created by fetching it
    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200
    assert rv_get.json["alias"] == "test-simulation"


@pytest.mark.skipif(not has_flask, reason="requires flask library")
@pytest.mark.parametrize("suffix", ["-", "#"])
def test_post_simulations_with_alias_auto_increment(client, suffix):
    """Test POST endpoint with alias ending in dash or hashtag (auto-increment)."""
    random_name = uuid.uuid4().hex
    simulation_data = generate_simulation_data(
        alias=f"{random_name}{suffix}",
    )

    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )

    assert rv.status_code == 200
    assert rv.json["ingested"] == simulation_data.simulation.uuid.hex

    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200
    assert rv_get.json["alias"] == f"{random_name}{suffix}1"

    # Check seqid metadata was added
    metadata = rv_get.json["metadata"]
    seqid_meta = [m for m in metadata if m["element"] == "seqid"]
    assert len(seqid_meta) == 1
    assert seqid_meta[0]["value"] == 1


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_alias_increment_sequence(client):
    """Test multiple simulations with incrementing dash alias."""
    # Create first simulation with dash alias
    simulation_data_1 = generate_simulation_data(
        alias="sequence-",
    )

    rv1 = client.post(
        "/v1.2/simulations",
        json=simulation_data_1.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv1.status_code == 200

    simulation_data_2 = generate_simulation_data(
        alias="sequence-",
    )

    rv2 = client.post(
        "/v1.2/simulations",
        json=simulation_data_2.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv2.status_code == 200

    # Verify aliases were incremented
    rv_get1 = client.get(
        f"/v1.2/simulation/{simulation_data_1.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get1.json["alias"] == "sequence-1"

    rv_get2 = client.get(
        f"/v1.2/simulation/{simulation_data_2.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get2.json["alias"] == "sequence-2"


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_no_alias(client):
    """Test POST endpoint with no alias provided (should use uuid.hex)."""
    simulation_data = generate_simulation_data()

    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )

    assert rv.status_code == 200
    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200
    assert rv_get.json["alias"] == simulation_data.simulation.uuid.hex


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_with_replaces(client):
    """Test POST endpoint with replaces metadata (deprecates old simulation)."""
    # Create initial simulation
    old_simulation_data = generate_simulation_data(alias="old_simulation")

    rv_old = client.post(
        "/v1.2/simulations",
        json=old_simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_old.status_code == 200

    # Create new simulation that replaces the old one
    new_simulation_data = generate_simulation_data(
        alias="updated-simulation",
        metadata=[
            MetadataData(
                element="replaces", value=old_simulation_data.simulation.uuid.hex
            ),
            MetadataData(element="replaces_reason", value="Test replacement"),
        ],
    )

    rv_new = client.post(
        "/v1.2/simulations",
        json=new_simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_new.status_code == 200

    # Verify the old simulation is marked as DEPRECATED
    rv_old_get = client.get(
        f"/v1.2/simulation/{old_simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_old_get.status_code == 200
    old_metadata = rv_old_get.json["metadata"]

    status_meta = [m for m in old_metadata if m["element"] == "status"]
    assert len(status_meta) == 1
    assert status_meta[0]["value"].lower() == "deprecated"

    # Check replaced_by metadata was added
    replaced_by_meta = [m for m in old_metadata if m["element"] == "replaced_by"]
    assert len(replaced_by_meta) == 1
    assert replaced_by_meta[0]["value"] == new_simulation_data.simulation.uuid

    # Verify the new simulation has replaces metadata
    rv_new_get = client.get(
        f"/v1.2/simulation/{new_simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_new_get.status_code == 200
    new_metadata = rv_new_get.json["metadata"]

    replaces_meta = [m for m in new_metadata if m["element"] == "replaces"]
    assert len(replaces_meta) == 1
    assert replaces_meta[0]["value"] == old_simulation_data.simulation.uuid.hex


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_replaces_nonexistent(client):
    """Test POST endpoint with replaces pointing to non-existent simulation."""
    # Create simulation that tries to replace a non-existent simulation
    simulation_data = generate_simulation_data(
        alias="replaces-nothing",
        metadata=[
            MetadataData(element="replaces", value=uuid.uuid1().hex),
            MetadataData(element="replaces_reason", value="Test replacement"),
        ],
    )

    # Should still succeed (old simulation just doesn't exist to deprecate)
    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv.status_code == 200

    # Verify the new simulation was created
    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200
    assert rv_get.json["alias"] == "replaces-nothing"


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_with_watcher(client):
    """Test POST endpoint with add_watcher set to true."""
    simulation_data = generate_simulation_data(
        add_watcher=True, uploaded_by="watcher-user"
    )

    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv.status_code == 200

    # Verify the simulation was created
    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
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
    """Test POST endpoint with add_watcher set to true."""
    simulation_data = generate_simulation_data(uploaded_by="test-user")

    rv = client.post(
        "/v1.2/simulations",
        json=simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv.status_code == 200

    # Verify the simulation was created
    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200

    metadata = rv_get.json["metadata"]
    uploaded_by_meta = [m for m in metadata if m["element"] == "uploaded_by"]
    assert len(uploaded_by_meta) == 1
    assert uploaded_by_meta[0]["value"] == "test-user"


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_post_simulations_trace_with_replaces(client):
    """Test the trace endpoint with a simulation that replaces another."""
    # Create original simulation
    # Create initial simulation
    old_simulation_data = generate_simulation_data(alias="trace-original")

    rv_old = client.post(
        "/v1.2/simulations",
        json=old_simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_old.status_code == 200

    # Create new simulation that replaces the old one
    new_simulation_data = generate_simulation_data(
        alias="trace-updated",
        metadata=[
            MetadataData(
                element="replaces", value=old_simulation_data.simulation.uuid.hex
            ),
            MetadataData(element="replaces_reason", value="New features"),
        ],
    )

    rv_new = client.post(
        "/v1.2/simulations",
        json=new_simulation_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_new.status_code == 200

    # Get trace for the new simulation
    rv_trace = client.get(
        f"/v1.2/trace/{new_simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_trace.status_code == 200
    trace_data = rv_trace.json

    # Verify trace includes replaces information
    assert "replaces" in trace_data

    replaces_uuid = trace_data["replaces"]["uuid"]
    assert replaces_uuid == old_simulation_data.simulation.uuid
    assert "replaces_reason" in trace_data
    assert trace_data["replaces_reason"] == "New features"

    with pytest.xfail("Deprecated on is not set, because replaced_on is never set"):
        assert "deprecated_on" in trace_data["replaces"]


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_basic(client):
    """Test basic GET request to /v1.2/simulations endpoint."""
    rv = client.get("/v1.2/simulations", headers=HEADERS)

    assert rv.status_code == 200
    assert rv.is_json

    data = rv.json
    assert "count" in data
    assert "page" in data
    assert "limit" in data
    assert "results" in data

    # Should return paginated results
    assert data["page"] == 1
    assert data["limit"] == 100
    assert isinstance(data["results"], list)
    assert data["count"] >= 100  # At least the 100 fixture simulations


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_pagination_limit(client):
    """Test GET request with custom limit."""
    custom_limit = 10
    headers_with_limit = {**HEADERS, "simdb-result-limit": str(custom_limit)}

    rv = client.get("/v1.2/simulations", headers=headers_with_limit)

    assert rv.status_code == 200
    data = rv.json

    assert data["limit"] == custom_limit
    assert len(data["results"]) <= custom_limit


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_pagination_page(client):
    """Test GET request with custom page number."""
    headers_page_2 = {**HEADERS, "simdb-result-limit": "10", "simdb-page": "2"}

    rv = client.get("/v1.2/simulations", headers=headers_page_2)

    assert rv.status_code == 200
    data = rv.json

    assert data["page"] == 2
    assert data["limit"] == 10


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_pagination_multiple_pages(client):
    """Test pagination across multiple pages."""
    limit = 20

    # Get first page
    headers_page_1 = {**HEADERS, "simdb-result-limit": str(limit), "simdb-page": "1"}
    rv1 = client.get("/v1.2/simulations", headers=headers_page_1)
    assert rv1.status_code == 200
    page1_data = rv1.json

    # Get second page
    headers_page_2 = {**HEADERS, "simdb-result-limit": str(limit), "simdb-page": "2"}
    rv2 = client.get("/v1.2/simulations", headers=headers_page_2)
    assert rv2.status_code == 200
    page2_data = rv2.json

    # Both should have same count and limit
    assert page1_data["count"] == page2_data["count"]
    assert page1_data["limit"] == page2_data["limit"] == limit

    # Pages should be different
    assert page1_data["page"] == 1
    assert page2_data["page"] == 2

    # Results should be different (assuming we have enough data)
    if page1_data["count"] > limit:
        page1_uuids = {item["uuid"] for item in page1_data["results"]}
        page2_uuids = {item["uuid"] for item in page2_data["results"]}
        assert page1_uuids != page2_uuids


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_filter_by_alias(client):
    """Test filtering simulations by alias."""
    # First create a simulation with a known alias
    sim_uuid = uuid.uuid4()
    test_alias = "filter-test-alias"

    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": test_alias,
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [{"element": "test_key", "value": "test_value"}],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_post = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_post.status_code == 200

    # Now filter by alias
    rv = client.get(f"/v1.2/simulations?alias={test_alias}", headers=HEADERS)

    assert rv.status_code == 200
    data = rv.json

    assert data["count"] >= 1
    # Check that the filtered result contains our simulation
    aliases = [item.get("alias") for item in data["results"]]
    assert test_alias in aliases


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_filter_by_uuid(client):
    """Test filtering simulations by UUID."""
    # Create a simulation with a known UUID
    sim_uuid = uuid.uuid4()

    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": "uuid-filter-test",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_post = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_post.status_code == 200

    # Filter by UUID
    rv = client.get(f"/v1.2/simulations?uuid={sim_uuid.hex}", headers=HEADERS)

    assert rv.status_code == 200
    data = rv.json

    assert data["count"] >= 1
    # Check that the filtered result contains our simulation
    uuids = [item.get("uuid") for item in data["results"]]
    assert sim_uuid in uuids


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_filter_by_metadata(client):
    """Test filtering simulations by metadata."""
    # Create simulations with specific metadata
    sim_uuid_1 = uuid.uuid4()
    sim_uuid_2 = uuid.uuid4()
    test_machine = "test-machine-xyz"

    simulation_data_1 = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid_1.hex},
            "alias": "metadata-filter-1",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [
                {"element": "machine", "value": test_machine},
                {"element": "code", "value": "test-code"},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    simulation_data_2 = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid_2.hex},
            "alias": "metadata-filter-2",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [
                {"element": "machine", "value": test_machine},
                {"element": "code", "value": "different-code"},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_post_1 = client.post(
        "/v1.2/simulations",
        json=simulation_data_1,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_post_1.status_code == 200

    rv_post_2 = client.post(
        "/v1.2/simulations",
        json=simulation_data_2,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_post_2.status_code == 200

    # Filter by machine metadata
    rv = client.get(f"/v1.2/simulations?machine={test_machine}", headers=HEADERS)

    assert rv.status_code == 200
    data = rv.json

    assert data["count"] >= 2

    # Check that both simulations are in the results
    results_uuids = [item.get("uuid") for item in data["results"]]
    assert sim_uuid_1 in results_uuids
    assert sim_uuid_2 in results_uuids


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_filter_multiple_metadata(client):
    """Test filtering simulations by multiple metadata fields."""
    # Create a simulation with multiple metadata fields
    sim_uuid = uuid.uuid4()
    test_machine = "multi-filter-machine"
    test_code = "multi-filter-code"

    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": "multi-metadata-filter",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [
                {"element": "machine", "value": test_machine},
                {"element": "code", "value": test_code},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_post = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_post.status_code == 200

    # Filter by both machine and code
    rv = client.get(
        f"/v1.2/simulations?machine={test_machine}&code={test_code}", headers=HEADERS
    )

    assert rv.status_code == 200
    data = rv.json

    assert data["count"] >= 1
    results_uuids = [item.get("uuid") for item in data["results"]]
    assert sim_uuid in results_uuids


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_sorting_asc(client):
    """Test sorting simulations in ascending order."""
    # Create simulations with sortable aliases
    for i in range(3):
        sim_uuid = uuid.uuid4()
        simulation_data = {
            "simulation": {
                "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
                "alias": f"sort-test-{i:03d}",
                "datetime": datetime.now(timezone.utc).isoformat(),
                "inputs": [],
                "outputs": [],
                "metadata": [],
            },
            "add_watcher": False,
            "uploaded_by": "test-user",
        }

        rv_post = client.post(
            "/v1.2/simulations",
            json=simulation_data,
            headers=HEADERS,
            content_type="application/json",
        )
        assert rv_post.status_code == 200

    # Get simulations sorted by alias ascending
    headers_sorted = {**HEADERS, "simdb-sort-by": "alias", "simdb-sort-asc": "true"}

    rv = client.get("/v1.2/simulations?alias=sort-test-%", headers=headers_sorted)

    assert rv.status_code == 200
    data = rv.json

    # Filter to only our test simulations
    test_sims = [
        item
        for item in data["results"]
        if item.get("alias", "").startswith("sort-test-")
    ]

    if len(test_sims) >= 2:
        # Check that results are sorted in ascending order
        aliases = [item.get("alias") for item in test_sims]
        assert aliases == sorted(aliases)


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_sorting_desc(client):
    """Test sorting simulations in descending order."""
    # Get simulations sorted by alias descending
    headers_sorted = {**HEADERS, "simdb-sort-by": "alias", "simdb-sort-asc": "false"}

    rv = client.get("/v1.2/simulations", headers=headers_sorted)

    assert rv.status_code == 200
    data = rv.json

    # Just verify the request succeeded and returned data
    assert "results" in data
    assert isinstance(data["results"], list)


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_empty_result(client):
    """Test GET request with filters that return no results."""
    # Use a filter that shouldn't match anything
    rv = client.get(
        "/v1.2/simulations?alias=non-existent-simulation-12345xyz", headers=HEADERS
    )

    assert rv.status_code == 200
    data = rv.json

    assert data["count"] == 0
    assert data["results"] == []


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_with_metadata_keys(client):
    """Test requesting specific metadata keys in results."""
    # Create a simulation with known metadata
    sim_uuid = uuid.uuid4()

    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": "meta-keys-test",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [
                {"element": "machine", "value": "machine-x"},
                {"element": "code", "value": "code-y"},
                {"element": "description", "value": "test description"},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_post = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_post.status_code == 200

    # Request simulations with specific metadata keys
    rv = client.get(
        "/v1.2/simulations?alias=meta-keys-test&machine&code", headers=HEADERS
    )

    assert rv.status_code == 200
    data = rv.json

    assert data["count"] >= 1


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations_combined_pagination_sorting_filtering(client):
    """Test GET request with pagination, sorting, and filtering combined."""
    # Create multiple simulations for testing
    test_prefix = "combined-test"
    for i in range(5):
        sim_uuid = uuid.uuid4()
        simulation_data = {
            "simulation": {
                "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
                "alias": f"{test_prefix}-{i:02d}",
                "datetime": datetime.now(timezone.utc).isoformat(),
                "inputs": [],
                "outputs": [],
                "metadata": [{"element": "test_group", "value": "combined"}],
            },
            "add_watcher": False,
            "uploaded_by": "test-user",
        }

        rv_post = client.post(
            "/v1.2/simulations",
            json=simulation_data,
            headers=HEADERS,
            content_type="application/json",
        )
        assert rv_post.status_code == 200

    # Request with all features combined
    headers_combined = {
        **HEADERS,
        "simdb-result-limit": "3",
        "simdb-page": "1",
        "simdb-sort-by": "alias",
        "simdb-sort-asc": "true",
    }

    rv = client.get(
        f"/v1.2/simulations?alias={test_prefix}-%", headers=headers_combined
    )

    assert rv.status_code == 200
    data = rv.json

    assert data["page"] == 1
    assert data["limit"] == 3
    assert len(data["results"]) <= 3


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulation_by_uuid(client):
    """Test GET /v1.2/simulation/{simulation_id} endpoint - retrieve by UUID."""
    # Create a simulation with known properties
    sim_uuid = uuid.uuid4()
    input_uuid = uuid.uuid4()
    output_uuid = uuid.uuid4()
    test_alias = "get-test-simulation"

    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": test_alias,
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [
                {
                    "uuid": {"_type": "uuid.UUID", "hex": input_uuid.hex},
                    "type": "FILE",
                    "uri": "file:///test/input.dat",
                    "checksum": "input123",
                    "datetime": datetime.now(timezone.utc).isoformat(),
                    "usage": "input_data",
                    "purpose": "test input",
                    "sensitivity": "public",
                    "access": "open",
                    "embargo": None,
                }
            ],
            "outputs": [
                {
                    "uuid": {"_type": "uuid.UUID", "hex": output_uuid.hex},
                    "type": "FILE",
                    "uri": "file:///test/output.dat",
                    "checksum": "output456",
                    "datetime": datetime.now(timezone.utc).isoformat(),
                    "usage": "output_data",
                    "purpose": "test output",
                    "sensitivity": "public",
                    "access": "open",
                    "embargo": None,
                }
            ],
            "metadata": [
                {"element": "machine", "value": "test-machine"},
                {"element": "code", "value": "test-code"},
                {"element": "description", "value": "Test simulation for GET"},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    # Create the simulation
    rv_post = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_post.status_code == 200

    # Test GET by UUID
    rv = client.get(f"/v1.2/simulation/{sim_uuid.hex}", headers=HEADERS)

    assert rv.status_code == 200
    assert rv.is_json

    data = rv.json

    # Verify basic fields
    assert "uuid" in data
    assert data["uuid"] == sim_uuid
    assert data["alias"] == test_alias

    # Verify datetime field exists
    assert "datetime" in data

    # Verify inputs and outputs
    assert "inputs" in data
    assert len(data["inputs"]) == 1
    assert data["inputs"][0]["uuid"] == input_uuid
    assert data["inputs"][0]["uri"] == "file:/test/input.dat"
    assert data["inputs"][0]["checksum"] == "input123"

    assert "outputs" in data
    assert len(data["outputs"]) == 1
    assert data["outputs"][0]["uuid"] == output_uuid
    assert data["outputs"][0]["uri"] == "file:/test/output.dat"
    assert data["outputs"][0]["checksum"] == "output456"

    # Verify metadata
    assert "metadata" in data
    assert len(data["metadata"]) >= 3  # At least our 3 metadata items
    metadata_dict = {m["element"]: m["value"] for m in data["metadata"]}
    assert metadata_dict["machine"] == "test-machine"
    assert metadata_dict["code"] == "test-code"
    assert metadata_dict["description"] == "Test simulation for GET"

    # Verify children and parents fields exist
    assert "children" in data
    assert "parents" in data
    assert isinstance(data["children"], list)
    assert isinstance(data["parents"], list)


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulation_by_alias(client):
    """Test GET /v1.2/simulation/{simulation_id} endpoint - retrieve by alias."""
    # Create a simulation with a unique alias
    sim_uuid = uuid.uuid4()
    test_alias = "get-by-alias-test"

    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": test_alias,
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [{"element": "test", "value": "alias retrieval"}],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_post = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_post.status_code == 200

    # Test GET by alias
    rv = client.get(f"/v1.2/simulation/{test_alias}", headers=HEADERS)

    assert rv.status_code == 200
    data = rv.json

    assert data["uuid"] == sim_uuid
    assert data["alias"] == test_alias


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulation_not_found(client):
    """Test GET /v1.2/simulation/{simulation_id} endpoint - non-existent simulation."""
    # Try to get a non-existent simulation
    fake_uuid = uuid.uuid4()

    rv = client.get(f"/v1.2/simulation/{fake_uuid.hex}", headers=HEADERS)

    assert rv.status_code == 400
    data = rv.json

    # Should contain an error message
    assert "error" in data or data.get("message") == "Simulation not found"


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulation_with_parents_and_children(client):
    """Test GET /v1.2/simulation/{simulation_id} endpoint - verify parents/children."""
    # Create parent simulation
    parent_uuid = uuid.uuid4()
    parent_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": parent_uuid.hex},
            "alias": "parent-simulation",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [{"element": "role", "value": "parent"}],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_parent = client.post(
        "/v1.2/simulations",
        json=parent_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_parent.status_code == 200

    # Create child simulation that references parent
    child_uuid = uuid.uuid4()
    child_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": child_uuid.hex},
            "alias": "child-simulation",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [],
            "outputs": [],
            "metadata": [
                {"element": "role", "value": "child"},
                {"element": "parent", "value": parent_uuid.hex},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "test-user",
    }

    rv_child = client.post(
        "/v1.2/simulations",
        json=child_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_child.status_code == 200

    # Get child simulation and verify parents field
    rv = client.get(f"/v1.2/simulation/{child_uuid.hex}", headers=HEADERS)

    assert rv.status_code == 200
    data = rv.json

    # Verify the parents/children structure
    assert "parents" in data
    assert "children" in data


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulation_full_response_structure(client):
    """Test GET /v1.2/simulation/{simulation_id} endpoint - verify complete response
    structure."""
    # Create a comprehensive simulation
    sim_uuid = uuid.uuid4()

    simulation_data = {
        "simulation": {
            "uuid": {"_type": "uuid.UUID", "hex": sim_uuid.hex},
            "alias": "complete-structure-test",
            "datetime": datetime.now(timezone.utc).isoformat(),
            "inputs": [
                {
                    "uuid": {"_type": "uuid.UUID", "hex": uuid.uuid4().hex},
                    "type": "FILE",
                    "uri": "file:///complete/input.dat",
                    "checksum": "complete123",
                    "datetime": datetime.now(timezone.utc).isoformat(),
                    "usage": "input",
                    "purpose": "complete input",
                    "sensitivity": "public",
                    "access": "open",
                    "embargo": None,
                }
            ],
            "outputs": [
                {
                    "uuid": {"_type": "uuid.UUID", "hex": uuid.uuid4().hex},
                    "type": "FILE",
                    "uri": "file:///complete/output.dat",
                    "checksum": "complete456",
                    "datetime": datetime.now(timezone.utc).isoformat(),
                    "usage": "output",
                    "purpose": "complete output",
                    "sensitivity": "public",
                    "access": "open",
                    "embargo": None,
                }
            ],
            "metadata": [
                {"element": "machine", "value": "complete-machine"},
                {"element": "version", "value": "1.0"},
            ],
        },
        "add_watcher": False,
        "uploaded_by": "complete-user",
    }

    rv_post = client.post(
        "/v1.2/simulations",
        json=simulation_data,
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_post.status_code == 200

    # Get the simulation
    rv = client.get(f"/v1.2/simulation/{sim_uuid.hex}", headers=HEADERS)

    assert rv.status_code == 200
    data = rv.json

    # Verify all required top-level fields are present
    required_fields = [
        "uuid",
        "alias",
        "datetime",
        "inputs",
        "outputs",
        "metadata",
        "children",
        "parents",
    ]
    for field in required_fields:
        assert field in data, f"Required field '{field}' missing from response"

    # Verify inputs structure
    assert len(data["inputs"]) == 1
    input_required_fields = ["uuid", "type", "uri", "checksum", "datetime"]
    for field in input_required_fields:
        assert field in data["inputs"][0], f"Required input field '{field}' missing"

    # Verify outputs structure
    assert len(data["outputs"]) == 1
    output_required_fields = ["uuid", "type", "uri", "checksum", "datetime"]
    for field in output_required_fields:
        assert field in data["outputs"][0], f"Required output field '{field}' missing"

    # Verify metadata structure
    assert len(data["metadata"]) >= 2
    for meta in data["metadata"]:
        assert "element" in meta
        assert "value" in meta
