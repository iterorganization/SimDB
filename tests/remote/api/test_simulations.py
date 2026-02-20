import uuid

import pytest
from conftest import (
    HEADERS,
    generate_simulation_data,
    generate_simulation_file,
    post_simulation,
)

from simdb.remote.models import (
    MetadataData,
    MetadataDataList,
    MetadataDeleteData,
    MetadataPatchData,
    PaginatedResponse,
    SimulationData,
    SimulationDataResponse,
    SimulationListItem,
    SimulationPostResponse,
    SimulationTraceData,
    StatusPatchData,
)


def test_get_root(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert "endpoints" in rv.json
    assert len(rv.json["endpoints"]) > 0
    assert all(
        endpoint.startswith("http://localhost/v") for endpoint in rv.json["endpoints"]
    )


def test_get_api_root(client):
    rv = client.get("/v1.2", headers=HEADERS)
    assert rv.status_code == 308


def test_post_simulations(client):
    """Test POST endpoint for creating a new simulation."""
    simulation_data = generate_simulation_data(
        alias="test-simulation",
        inputs=[generate_simulation_file()],
        outputs=[generate_simulation_file()],
    )

    # POST the simulation
    rv = post_simulation(client, simulation_data)

    # Verify the response
    assert rv.status_code == 200

    result = SimulationPostResponse.model_validate(rv.json)
    assert result.ingested == simulation_data.simulation.uuid

    # Verify the simulation was created by fetching it
    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200
    result = SimulationDataResponse.model_validate(rv_get.json)
    assert result.alias == simulation_data.simulation.alias


@pytest.mark.parametrize("suffix", ["-", "#"])
def test_post_simulations_with_alias_auto_increment(client, suffix):
    """Test POST endpoint with alias ending in dash or hashtag (auto-increment)."""
    random_name = uuid.uuid4().hex
    simulation_data = generate_simulation_data(
        alias=f"{random_name}{suffix}",
    )

    rv = post_simulation(client, simulation_data)

    assert rv.status_code == 200
    result = SimulationPostResponse.model_validate(rv.json)
    assert result.ingested == simulation_data.simulation.uuid

    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200
    result = SimulationDataResponse.model_validate(rv_get.json)
    assert result.alias == f"{random_name}{suffix}1"

    # Check seqid metadata was added
    assert result.metadata.as_dict()["seqid"] == 1


def test_post_simulations_alias_increment_sequence(client):
    """Test multiple simulations with incrementing dash alias."""
    # Create first simulation with dash alias
    simulation_data_1 = generate_simulation_data(
        alias="sequence-",
    )

    rv1 = post_simulation(client, simulation_data_1)
    assert rv1.status_code == 200

    simulation_data_2 = generate_simulation_data(
        alias="sequence-",
    )

    rv2 = post_simulation(client, simulation_data_2)
    assert rv2.status_code == 200

    # Verify aliases were incremented
    rv_get1 = client.get(
        f"/v1.2/simulation/{simulation_data_1.simulation.uuid.hex}", headers=HEADERS
    )
    result = SimulationDataResponse.model_validate(rv_get1.json)
    assert result.alias == "sequence-1"

    rv_get2 = client.get(
        f"/v1.2/simulation/{simulation_data_2.simulation.uuid.hex}", headers=HEADERS
    )
    result = SimulationDataResponse.model_validate(rv_get2.json)
    assert result.alias == "sequence-2"


@pytest.mark.xfail(reason="Alias is required in current API")
def test_post_simulations_no_alias(client):
    """Test POST endpoint with no alias provided (should use uuid.hex)."""
    simulation_data = generate_simulation_data()

    rv = post_simulation(client, simulation_data)

    assert rv.status_code == 200
    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200
    result = SimulationDataResponse.model_validate(rv_get.json)
    assert result.alias == simulation_data.simulation.uuid


def test_post_simulations_with_replaces(client):
    """Test POST endpoint with replaces metadata (deprecates old simulation)."""
    # Create initial simulation
    old_simulation_data = generate_simulation_data(alias="old_simulation")

    rv_old = post_simulation(client, old_simulation_data)
    assert rv_old.status_code == 200

    # Create new simulation that replaces the old one
    new_simulation_data = generate_simulation_data(
        alias="updated-simulation",
        metadata=[
            MetadataData(
                # This needs to be the hex representation
                element="replaces",
                value=old_simulation_data.simulation.uuid.hex,
            ),
            MetadataData(element="replaces_reason", value="Test replacement"),
        ],
    )

    rv_new = post_simulation(client, new_simulation_data)
    assert rv_new.status_code == 200

    # Verify the old simulation is marked as DEPRECATED
    rv_old_get = client.get(
        f"/v1.2/simulation/{old_simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_old_get.status_code == 200
    result = SimulationDataResponse.model_validate(rv_old_get.json)
    metadata = result.metadata.as_dict()
    assert metadata["status"].lower() == "deprecated"

    # Check replaced_by metadata was added
    assert metadata["replaced_by"] == new_simulation_data.simulation.uuid

    # Verify the new simulation has replaces metadata
    rv_new_get = client.get(
        f"/v1.2/simulation/{new_simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_new_get.status_code == 200
    result = SimulationDataResponse.model_validate(rv_new_get.json)
    metadata = result.metadata.as_dict()

    # This will be the hex representation
    assert metadata["replaces"] == old_simulation_data.simulation.uuid.hex


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
    rv = post_simulation(client, simulation_data)
    assert rv.status_code == 200

    # Verify the new simulation was created
    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200
    result = SimulationDataResponse.model_validate(rv_get.json)
    assert result.alias == "replaces-nothing"


@pytest.mark.xfail(
    reason="User.email is not set for admin without custom authenticators"
)
def test_post_simulations_with_watcher(client):
    """Test POST endpoint with add_watcher set to true."""
    simulation_data = generate_simulation_data(
        add_watcher=True, uploaded_by="watcher-user"
    )

    rv = post_simulation(client, simulation_data)
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


def test_post_simulations_uploaded_by(client):
    """Test POST endpoint with uploaded_by field."""
    """Test POST endpoint with add_watcher set to true."""
    simulation_data = generate_simulation_data(uploaded_by="test-user")

    rv = post_simulation(client, simulation_data)
    assert rv.status_code == 200

    # Verify the simulation was created
    rv_get = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )
    assert rv_get.status_code == 200
    result = SimulationDataResponse.model_validate(rv_get.json)
    assert result.metadata.as_dict()["uploaded_by"] == "test-user"


def test_get_simulations_basic(client):
    """Test basic GET request to /v1.2/simulations endpoint."""
    rv = client.get("/v1.2/simulations", headers=HEADERS)

    assert rv.status_code == 200
    assert rv.is_json

    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    assert data.page == 1
    assert data.limit == 100
    assert data.count >= 100


def test_get_simulations_pagination_limit(client):
    """Test GET request with custom limit."""
    custom_limit = 10
    headers_with_limit = {**HEADERS, "simdb-result-limit": str(custom_limit)}

    rv = client.get("/v1.2/simulations", headers=headers_with_limit)

    assert rv.status_code == 200
    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    assert data.limit == custom_limit
    assert len(data.results) <= custom_limit


def test_get_simulations_pagination_page(client):
    """Test GET request with custom page number."""
    headers_page_2 = {**HEADERS, "simdb-result-limit": "10", "simdb-page": "2"}

    rv = client.get("/v1.2/simulations", headers=headers_page_2)

    assert rv.status_code == 200
    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    assert data.page == 2
    assert data.limit == 10


def test_get_simulations_pagination_multiple_pages(client):
    """Test pagination across multiple pages."""
    limit = 20

    # Get first page
    headers_page_1 = {**HEADERS, "simdb-result-limit": str(limit), "simdb-page": "1"}
    rv1 = client.get("/v1.2/simulations", headers=headers_page_1)
    assert rv1.status_code == 200
    page1_data = PaginatedResponse[SimulationListItem].model_validate(rv1.json)

    # Get second page
    headers_page_2 = {**HEADERS, "simdb-result-limit": str(limit), "simdb-page": "2"}
    rv2 = client.get("/v1.2/simulations", headers=headers_page_2)
    assert rv2.status_code == 200
    page2_data = PaginatedResponse[SimulationListItem].model_validate(rv2.json)

    # Both should have same count and limit
    assert page1_data.count == page2_data.count
    assert page1_data.limit == page2_data.limit == limit

    # Pages should be different
    assert page1_data.page == 1
    assert page2_data.page == 2

    page1_uuids = {item.uuid for item in page1_data.results}
    page2_uuids = {item.uuid for item in page2_data.results}
    assert page1_uuids != page2_uuids


def test_get_simulations_filter_by_alias(client):
    """Test filtering simulations by alias."""
    # First create a simulation with a known alias
    test_alias = "filter-test-alias"
    simulation_data = generate_simulation_data(alias=test_alias)

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    # Now filter by alias
    rv = client.get(f"/v1.2/simulations?alias={test_alias}", headers=HEADERS)

    assert rv.status_code == 200
    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    assert data.count == 1
    # Check that the filtered result contains our simulation
    aliases = [item.alias for item in data.results]
    assert test_alias in aliases


def test_get_simulations_filter_by_uuid(client):
    """Test filtering simulations by UUID."""
    # Create a simulation with a known UUID
    simulation_data = generate_simulation_data()

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    # Filter by UUID
    rv = client.get(
        f"/v1.2/simulations?uuid={simulation_data.simulation.uuid.hex}", headers=HEADERS
    )

    assert rv.status_code == 200
    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    assert data.count == 1
    # Check that the filtered result contains our simulation
    uuids = [item.uuid for item in data.results]
    assert simulation_data.simulation.uuid in uuids


def test_get_simulations_filter_by_metadata(client):
    """Test filtering simulations by metadata."""
    # Create simulations with specific metadata
    test_metadata = MetadataData(element="machine", value="test_machine")

    simulation_data_1 = generate_simulation_data(metadata=[test_metadata])
    simulation_data_2 = generate_simulation_data(metadata=[test_metadata])
    rv_post_1 = post_simulation(client, simulation_data_1)
    assert rv_post_1.status_code == 200

    rv_post_2 = post_simulation(client, simulation_data_2)
    assert rv_post_2.status_code == 200

    # Filter by machine metadata
    rv = client.get(
        f"/v1.2/simulations?{test_metadata.as_querystring()}",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    assert data.count == 2

    # Check that both simulations are in the results
    results_uuids = [item.uuid for item in data.results]
    assert simulation_data_1.simulation.uuid in results_uuids
    assert simulation_data_2.simulation.uuid in results_uuids


def test_get_simulations_filter_multiple_metadata(client):
    """Test filtering simulations by multiple metadata fields."""
    # Create a simulation with multiple metadata fields
    test_metadata = {"machine": "multi-filter-machine", "code": "multi-filter-code"}

    simulation_data = generate_simulation_data(metadata=test_metadata)

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    # Filter by both machine and code
    rv = client.get(
        f"/v1.2/simulations?{simulation_data.simulation.metadata.as_querystring()}",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    assert data.count == 1
    results_uuids = [item.uuid for item in data.results]
    assert simulation_data.simulation.uuid in results_uuids


@pytest.mark.xfail(reason="Only sorting by metadata keys works for now")
def test_get_simulations_alias_sorting_asc(client):
    """Test sorting simulations in ascending order by alias."""
    # Create simulations with sortable aliases
    for i in range(3):
        simulation_data = generate_simulation_data(alias=f"alias-sort-test-{i:03d}")

        rv_post = post_simulation(client, simulation_data)
        assert rv_post.status_code == 200

    # Get simulations sorted by alias ascending
    headers_sorted = {**HEADERS, "simdb-sort-by": "alias", "simdb-sort-asc": "true"}

    rv = client.get(
        "/v1.2/simulations?alias=IN%3Aalias-sort-test-", headers=headers_sorted
    )

    assert rv.status_code == 200
    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    # Check that results are sorted in ascending order
    aliases = [item.alias for item in data.results if item.alias is not None]
    assert aliases == sorted(aliases)
    assert len(aliases) == 3


@pytest.mark.parametrize("ascending", [True, False])
def test_get_simulations_metadata_sorting(client, ascending):
    """Test sorting simulations in ascending order."""
    # Create simulations with sortable aliases
    # post them in the order: 2 1 0 5 4 3
    # ascending should result in 0 1 2 3 4 5
    # descending should result in 5 4 3 2 1 0
    for i in reversed(range(3)):
        simulation_data = generate_simulation_data(
            alias=f"sort-test-{ascending}-{i:03d}",
            metadata=[MetadataData(element="sort-test", value=i)],
        )

        rv_post = post_simulation(client, simulation_data)
        assert rv_post.status_code == 200

    for i in reversed(range(3, 6)):
        simulation_data = generate_simulation_data(
            alias=f"sort-test-{ascending}-{i:03d}",
            metadata=[MetadataData(element="sort-test", value=i)],
        )

        rv_post = post_simulation(client, simulation_data)
        assert rv_post.status_code == 200

    # Get simulations sorted by alias ascending
    headers_sorted = {
        **HEADERS,
        "simdb-sort-by": "sort-test",
        "simdb-sort-asc": "true" if ascending else "false",
    }

    rv = client.get(
        f"/v1.2/simulations?alias=IN%3Asort-test-{ascending}&sort-test",
        headers=headers_sorted,
    )

    assert rv.status_code == 200
    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    # Check that results are sorted in the correct order
    metadata = [
        item.metadata[0].value for item in data.results if item.metadata is not None
    ]
    assert metadata == sorted(metadata, reverse=not ascending)
    assert len(metadata) == 6


def test_get_simulations_empty_result(client):
    """Test GET request with filters that return no results."""
    # Use a filter that shouldn't match anything
    rv = client.get(
        "/v1.2/simulations?alias=non-existent-simulation-12345xyz", headers=HEADERS
    )

    assert rv.status_code == 200
    data = PaginatedResponse[SimulationListItem].model_validate(rv.json)

    assert data.count == 0
    assert len(data.results) == 0


def test_get_simulations_with_metadata_keys(client):
    """Test requesting specific metadata keys in results."""
    # Create a simulation with known metadata

    simulation_data = generate_simulation_data(
        alias="meta-keys-test",
        metadata={"machine": "machine-x", "code": "code-y"},
    )

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    # Request simulations with specific metadata keys
    rv = client.get(
        "/v1.2/simulations?alias=meta-keys-test&machine&code", headers=HEADERS
    )

    assert rv.status_code == 200
    data: PaginatedResponse[SimulationListItem] = PaginatedResponse[
        SimulationListItem
    ].model_validate(rv.json)

    assert data.count == 1
    assert len(data.results) == 1


def test_get_simulation_by_uuid(client):
    """Test GET /v1.2/simulation/{simulation_id} endpoint - retrieve by UUID."""
    # Create a simulation with known properties
    simulation_data = generate_simulation_data(uploaded_by="test-uploader")

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    # Test GET by UUID
    rv = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )

    assert rv.status_code == 200
    assert rv.is_json

    # Validate full data model
    SimulationDataResponse.model_validate(rv.json)

    simulation_data_received = SimulationData.model_validate(rv.json, extra="ignore")
    simulation_data_check = simulation_data.simulation.model_copy()

    # fill fields that are filled by the server
    simulation_data_check.metadata = MetadataDataList.model_validate(
        {"uploaded_by": simulation_data.uploaded_by}
    )

    # datetime gets updated by the server
    simulation_data_check.datetime = simulation_data_received.datetime

    assert simulation_data_received == simulation_data_check


def test_get_simulation_by_alias(client):
    """Test GET /v1.2/simulation/{simulation_id} endpoint - retrieve by alias."""
    # Create a simulation with a unique alias
    simulation_data = generate_simulation_data(
        alias="test-get-alias", uploaded_by="test-uploader"
    )

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    # Test GET by alias
    rv = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.alias}", headers=HEADERS
    )

    assert rv.status_code == 200
    assert rv.is_json

    # Validate full data model
    SimulationDataResponse.model_validate(rv.json)

    simulation_data_received = SimulationData.model_validate(rv.json, extra="ignore")
    simulation_data_check = simulation_data.simulation.model_copy()

    # fill fields that are filled by the server
    simulation_data_check.metadata = MetadataDataList.model_validate(
        {"uploaded_by": simulation_data.uploaded_by}
    )

    # datetime gets updated by the server
    simulation_data_check.datetime = simulation_data_received.datetime

    assert simulation_data_received == simulation_data_check


def test_get_simulation_not_found(client):
    """Test GET /v1.2/simulation/{simulation_id} endpoint - non-existent simulation."""
    # Try to get a non-existent simulation
    fake_uuid = uuid.uuid1()

    rv = client.get(f"/v1.2/simulation/{fake_uuid.hex}", headers=HEADERS)

    assert rv.status_code == 400
    data = rv.json

    # Should contain an error message
    assert "error" in data or data.get("message") == "Simulation not found"


def test_get_simulation_metadata(client):
    """Test GET /v1.2/simulation/metadata/{simulation_id} endpoint."""
    simulation_data = generate_simulation_data(
        metadata={"metadata-a": "abc", "metadata-b": "123"}, uploaded_by="test-user"
    )

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    rv = client.get(
        f"/v1.2/simulation/metadata/{simulation_data.simulation.uuid.hex}",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    data = MetadataDataList.model_validate(rv.json)
    check_data = simulation_data.simulation.metadata.model_copy()
    check_data.root.append(MetadataData(element="uploaded_by", value="test-user"))
    assert data == simulation_data.simulation.metadata


def test_patch_simulation(client):
    """Test PATCH /v1.2/simulation/{simulation_id} endpoint."""
    simulation_data = generate_simulation_data()

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    rv = client.patch(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}",
        json=StatusPatchData(status="failed").model_dump(mode="json"),
        headers=HEADERS,
    )

    assert rv.status_code == 200

    # Status is never returned, so we can't check if it is set


def test_delete_simulation(client):
    """Test DELETE /v1.2/simulation/{simulation_id} endpoint."""
    simulation_data = generate_simulation_data()

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    rv = client.delete(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}",
        headers=HEADERS,
    )

    assert rv.status_code == 200

    rv = client.get(
        f"/v1.2/simulation/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )

    assert rv.status_code == 400


def test_patch_simulation_metadata(client):
    """Test PATCH /v1.2/simulation/metadata/{simulation_id} endpoint."""
    simulation_data = generate_simulation_data(
        metadata={"metadata-a": "abc"}, uploaded_by="test-user"
    )

    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    rv = client.patch(
        f"/v1.2/simulation/metadata/{simulation_data.simulation.uuid.hex}",
        json=MetadataPatchData(key="metadata-a", value="def").model_dump(mode="json"),
        headers=HEADERS,
    )

    assert rv.status_code == 200

    rv = client.get(
        f"/v1.2/simulation/metadata/{simulation_data.simulation.uuid.hex}",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    data = MetadataDataList.model_validate(rv.json)
    check_data = simulation_data.simulation.metadata.model_copy()
    check_data[0].value = "def"
    check_data.root.append(MetadataData(element="uploaded_by", value="test-user"))
    assert data == simulation_data.simulation.metadata


def test_delete_simulation_metadata(client):
    """Test DELETE /v1.2/simulation/metadata/{simulation_id} endpoint."""
    simulation_data = generate_simulation_data(
        metadata={"metadata-a": "abc"}, uploaded_by="test-user"
    )

    rv_post = post_simulation(client, simulation_data)
    print(rv_post.data)
    print(simulation_data)
    assert rv_post.status_code == 200

    rv = client.delete(
        f"/v1.2/simulation/metadata/{simulation_data.simulation.uuid.hex}",
        json=MetadataDeleteData(key="metadata-a").model_dump(mode="json"),
        headers=HEADERS,
    )

    assert rv.status_code == 200

    rv = client.get(
        f"/v1.2/simulation/metadata/{simulation_data.simulation.uuid.hex}",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    data = MetadataDataList.model_validate(rv.json)
    check_data = simulation_data.simulation.metadata.model_copy()
    check_data.root.pop()
    check_data.root.append(MetadataData(element="uploaded_by", value="test-user"))
    assert data == simulation_data.simulation.metadata


def test_trace_endpoint(client):
    """Test trace endpoint returns valid SimulationTraceData and handles replacement
    chains."""
    # Create v1 -> v2 -> v3 replacement chain
    sim_v1 = generate_simulation_data(alias="trace-v1")
    rv1 = post_simulation(client, sim_v1)
    assert rv1.status_code == 200

    sim_v2 = generate_simulation_data(
        alias="trace-v2",
        metadata=[
            MetadataData(element="replaces", value=sim_v1.simulation.uuid.hex),
            MetadataData(element="replaces_reason", value="Bug fixes"),
        ],
    )
    rv2 = post_simulation(client, sim_v2)
    assert rv2.status_code == 200

    sim_v3 = generate_simulation_data(
        alias="trace-v3",
        metadata=[
            MetadataData(element="replaces", value=sim_v2.simulation.uuid.hex),
            MetadataData(element="replaces_reason", value="Performance"),
        ],
    )
    rv3 = post_simulation(client, sim_v3)
    assert rv3.status_code == 200

    # Test trace for v3 (full chain)
    rv_trace = client.get(f"/v1.2/trace/{sim_v3.simulation.uuid.hex}", headers=HEADERS)
    assert rv_trace.status_code == 200

    trace = SimulationTraceData.model_validate(rv_trace.json)

    # Verify v3
    assert trace.uuid == sim_v3.simulation.uuid
    assert trace.alias == "trace-v3"
    assert trace.replaces_reason == "Performance"

    # Verify v2 (nested)
    assert trace.replaces is not None
    assert trace.replaces.uuid == sim_v2.simulation.uuid
    assert trace.replaces.replaces_reason == "Bug fixes"

    # Verify v1 (double nested)
    assert trace.replaces.replaces is not None
    assert trace.replaces.replaces.uuid == sim_v1.simulation.uuid
    assert trace.replaces.replaces.replaces is None
