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

# The ways a simulation can be referred to, as documented for SIM_ID.
SIM_REFS = {
    "uuid": lambda uuid: uuid.hex,
    "short_uuid": lambda uuid: uuid.hex[:8],
    "alias": lambda uuid: ALIAS,
}


@pytest.fixture
def sim_uuid(client):
    """UUID of a posted simulation with alias ALIAS."""
    simulation_data = generate_simulation_data(alias=ALIAS)
    rv_post = post_simulation(client, simulation_data)
    assert rv_post.status_code == 200
    return simulation_data.simulation.uuid


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


def test_get_watchers(client, sim_uuid):
    """Test GET /v1.2/watchers/{simulation_id} endpoint."""
    rv = client.get(f"/v1.2/watchers/{sim_uuid.hex}", headers=HEADERS)

    assert rv.status_code == 200
    assert WatcherGetResponse.model_validate(rv.json).root == []


def test_get_watchers_after_add(client, sim_uuid):
    """Test GET /v1.2/watchers/{simulation_id} endpoint - with a watcher."""
    assert _add_watcher(client, sim_uuid.hex).status_code == 200

    rv = client.get(f"/v1.2/watchers/{sim_uuid.hex}", headers=HEADERS)

    assert rv.status_code == 200, rv.json
    (watcher,) = WatcherGetResponse.model_validate(rv.json).root
    assert watcher.username == "testuser"
    assert watcher.notification == "A"


@pytest.mark.parametrize("ref", SIM_REFS)
def test_post_watchers(client, sim_uuid, ref):
    """Test POST /v1.2/watchers/{simulation_id} endpoint - add watcher."""
    rv = _add_watcher(client, SIM_REFS[ref](sim_uuid))

    assert rv.status_code == 200, rv.json
    data = WatcherPostResponse.model_validate(rv.json)
    assert data.added.simulation == sim_uuid


@pytest.mark.parametrize("ref", SIM_REFS)
def test_delete_watchers(client, sim_uuid, ref):
    """Test DELETE /v1.2/watchers/{simulation_id} endpoint - remove watcher."""
    sim_ref = SIM_REFS[ref](sim_uuid)
    assert _add_watcher(client, sim_ref).status_code == 200

    rv = _remove_watcher(client, sim_ref)

    assert rv.status_code == 200, rv.json
    data = WatcherDeleteResponse.model_validate(rv.json)
    assert data.removed.simulation == sim_uuid


def test_watchers_unknown_simulation(client):
    """Watcher endpoints return 404 for a simulation that does not exist."""
    assert client.get("/v1.2/watchers/999999/9", headers=HEADERS).status_code == 404
    assert _add_watcher(client, "999999/9").status_code == 404
    assert _remove_watcher(client, "999999/9").status_code == 404


def test_delete_watchers_not_watching(client, sim_uuid):
    """DELETE returns 404 when the user is not watching the simulation."""
    rv = _remove_watcher(client, sim_uuid.hex)

    assert rv.status_code == 404
