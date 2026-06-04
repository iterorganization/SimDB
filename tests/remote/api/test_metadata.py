from conftest import (
    HEADERS,
    generate_simulation_data,
    post_simulation,
)

from simdb.remote.models import MetadataKeyInfoList, MetadataValueList, RangeValue


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


def test_get_metadata_range_value(client):
    """Test metadata Range storage"""
    # Create a simulation with a range metadata value
    range_data = RangeValue(min=1.0, max=3.0)
    simulation_data_1 = generate_simulation_data(metadata={"range_machine": range_data})
    rv_post_1 = post_simulation(client, simulation_data_1)
    assert rv_post_1.status_code == 200

    rv = client.get("/v1.2/metadata", headers=HEADERS)
    assert rv.status_code == 200
    mkeys = MetadataKeyInfoList.model_validate_json(rv.data)
    mkey = next((k for k in mkeys.root if k.name == "range_machine"), None)
    assert mkey is not None, "range_machine key not found in metadata keys"
    assert mkey.type == "Range"

    rv = client.get("/v1.2/metadata/range_machine", headers=HEADERS)

    assert rv.status_code == 200
    mdata = MetadataValueList.model_validate_json(rv.data)
    assert len(mdata.root) == 1
    a = mdata.root[0]
    assert isinstance(a, RangeValue)
    assert a.min == 1.0
    assert a.max == 3.0


def test_get_metadata_values_nonexistent_key(client):
    """Test GET /v1.2/metadata/{name} endpoint - non-existent key."""
    # Get values for a metadata key that doesn't exist
    rv = client.get("/v1.2/metadata/nonexistent-key", headers=HEADERS)

    assert rv.status_code == 200
    # Should return an empty list or list without the key
    assert isinstance(rv.json, list)
