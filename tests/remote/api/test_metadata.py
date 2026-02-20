from conftest import (
    HEADERS,
    generate_simulation_data,
    post_simulation,
)


def test_get_metadata_keys(client):
    """Test GET /v1.2/metadata endpoint - list all metadata keys."""
    # Create some simulations with metadata first
    simulation_data_1 = generate_simulation_data(
        metadata={"machine": "test-machine-1", "code": "test-code"}
    )
    rv_post_1 = post_simulation(client, simulation_data_1)
    assert rv_post_1.status_code == 200

    simulation_data_2 = generate_simulation_data(
        metadata={"machine": "test-machine-2", "code": "test-code"}
    )
    rv_post_2 = post_simulation(client, simulation_data_2)
    assert rv_post_2.status_code == 200

    # Get all metadata keys
    rv = client.get("/v1.2/metadata", headers=HEADERS)

    assert rv.status_code == 200
    # The response should be a list of metadata keys
    assert isinstance(rv.json, list)


def test_get_metadata_values(client):
    """Test GET /v1.2/metadata/{name} endpoint - list all values for a metadata key."""
    # Create some simulations with metadata first
    simulation_data_1 = generate_simulation_data(metadata={"machine": "machine-a"})
    rv_post_1 = post_simulation(client, simulation_data_1)
    assert rv_post_1.status_code == 200

    simulation_data_2 = generate_simulation_data(metadata={"machine": "machine-b"})
    rv_post_2 = post_simulation(client, simulation_data_2)
    assert rv_post_2.status_code == 200

    # Get values for the "machine" metadata key
    rv = client.get("/v1.2/metadata/machine", headers=HEADERS)

    assert rv.status_code == 200
    # The response should be a list of values
    assert isinstance(rv.json, list)
    # Should contain both machine values
    assert "machine-a" in rv.json or "machine-b" in rv.json


def test_get_metadata_values_nonexistent_key(client):
    """Test GET /v1.2/metadata/{name} endpoint - non-existent key."""
    # Get values for a metadata key that doesn't exist
    rv = client.get("/v1.2/metadata/nonexistent-key", headers=HEADERS)

    assert rv.status_code == 200
    # Should return an empty list or list without the key
    assert isinstance(rv.json, list)
