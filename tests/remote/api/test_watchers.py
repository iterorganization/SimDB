from conftest import (
    HEADERS,
    generate_simulation_data,
    post_simulation,
)

from simdb.remote.models import (
    WatcherDeleteRequest,
    WatcherDeleteResponse,
    WatcherGetResponse,
    WatcherPostRequest,
    WatcherPostResponse,
)


def test_get_watchers(client):
    """Test GET /v1.2/watchers/{simulation_id} endpoint."""
    # Create a simulation first
    simulation_data = generate_simulation_data()
    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    # Get watchers for the simulation
    rv = client.get(
        f"/v1.2/watchers/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )

    assert rv.status_code == 200
    WatcherGetResponse.model_validate(rv.json)


def test_post_watchers(client):
    """Test POST /v1.2/watchers/{simulation_id} endpoint - add watcher."""
    # Create a simulation first
    simulation_data = generate_simulation_data()
    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    post_data = WatcherPostRequest(
        user="testuser", email="example@iter.org", notification="ALL"
    )
    # Add a watcher to the simulation
    rv = client.post(
        f"/v1.2/watchers/{simulation_data.simulation.uuid.hex}",
        json=post_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )

    assert rv.status_code == 200
    data = WatcherPostResponse.model_validate(rv.json)
    assert data.added.simulation == simulation_data.simulation.uuid


def test_delete_watchers(client):
    """Test DELETE /v1.2/watchers/{simulation_id} endpoint - remove watcher."""
    # Create a simulation first
    simulation_data = generate_simulation_data()
    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200

    post_data = WatcherPostRequest(
        user="testuser", email="example@iter.org", notification="ALL"
    )
    # Add a watcher first
    rv_add = client.post(
        f"/v1.2/watchers/{simulation_data.simulation.uuid.hex}",
        json=post_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_add.status_code == 200

    post_data = WatcherDeleteRequest(user="testuser")
    # Remove the watcher
    rv = client.delete(
        f"/v1.2/watchers/{simulation_data.simulation.uuid.hex}",
        json=post_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )

    assert rv.status_code == 200
    data = WatcherDeleteResponse.model_validate(rv.json)
    assert data.removed.simulation == simulation_data.simulation.uuid
