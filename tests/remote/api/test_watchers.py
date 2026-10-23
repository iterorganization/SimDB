import pytest
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

ALIAS = "100001/1"


@pytest.fixture(params=["uuid", "alias"])
def simulation(client, request):
    """A posted simulation and the reference (UUID or alias) to address it by."""
    simulation_data = generate_simulation_data(alias=ALIAS)
    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200
    uuid = simulation_data.simulation.uuid
    sim_ref = uuid.hex if request.param == "uuid" else ALIAS
    return uuid, sim_ref


def _add_watcher(client, sim_ref):
    post_data = WatcherPostRequest(
        user="testuser", email="example@iter.org", notification="ALL"
    )
    return client.post(
        f"/v1.2/watchers/{sim_ref}",
        json=post_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )


def _remove_watcher(client, sim_ref):
    delete_data = WatcherDeleteRequest(user="testuser")
    return client.delete(
        f"/v1.2/watchers/{sim_ref}",
        json=delete_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )


def test_get_watchers(client, simulation):
    """Test GET /v1.2/watchers/{simulation_id} endpoint."""
    _, sim_ref = simulation
    rv = client.get(f"/v1.2/watchers/{sim_ref}", headers=HEADERS)

    assert rv.status_code == 200
    assert WatcherGetResponse.model_validate(rv.json).root == []


def test_get_watchers_after_add(client, simulation):
    """Test GET /v1.2/watchers/{simulation_id} endpoint - with a watcher."""
    _, sim_ref = simulation
    assert _add_watcher(client, sim_ref).status_code == 200

    rv = client.get(f"/v1.2/watchers/{sim_ref}", headers=HEADERS)

    assert rv.status_code == 200, rv.json
    (watcher,) = WatcherGetResponse.model_validate(rv.json).root
    assert watcher.username == "testuser"
    assert watcher.notification == "A"


def test_post_watchers(client, simulation):
    """Test POST /v1.2/watchers/{simulation_id} endpoint - add watcher."""
    uuid, sim_ref = simulation
    rv = _add_watcher(client, sim_ref)

    assert rv.status_code == 200, rv.json
    data = WatcherPostResponse.model_validate(rv.json)
    assert data.added.simulation == uuid


def test_delete_watchers(client, simulation):
    """Test DELETE /v1.2/watchers/{simulation_id} endpoint - remove watcher."""
    uuid, sim_ref = simulation
    assert _add_watcher(client, sim_ref).status_code == 200

    rv = _remove_watcher(client, sim_ref)

    assert rv.status_code == 200, rv.json
    data = WatcherDeleteResponse.model_validate(rv.json)
    assert data.removed.simulation == uuid
