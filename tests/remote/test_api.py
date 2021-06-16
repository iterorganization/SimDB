import base64
import os
import pytest
import tempfile
try:
    import flask
    has_flask = True
except ImportError:
    has_flask = False

from simdb.database.models import Simulation
from simdb.cli.manifest import Manifest

TEST_PASSWORD = "test123"
CREDENTIALS = base64.b64encode(f'admin:{TEST_PASSWORD}'.encode()).decode()
HEADERS = {"Authorization": f'Basic {CREDENTIALS}'}

SIMULATIONS = []
for _ in range(100):
    SIMULATIONS.append(Simulation(Manifest()))


@pytest.fixture
def client():
    from simdb.remote.app import create_app
    from simdb.config import Config
    from simdb.remote.api import api
    config = Config()
    config.load()
    db_fd, db_file = tempfile.mkstemp()
    config.set_option("database.type", "sqlite")
    config.set_option("database.file", db_file)
    config.set_option("server.admin_password", TEST_PASSWORD)
    app = create_app(config=config, testing=True, debug=True)

    for sim in SIMULATIONS:
        api.db.insert_simulation(sim)

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(app.simdb_config.get_option("database.file"))


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_root(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert rv.json == {'endpoints': ['http://localhost/api/v1']}


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_api_root(client):
    rv = client.get("/api/v1/", headers=HEADERS)
    assert rv.status_code == 200


@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_get_simulations(client):
    rv = client.get("/api/v1/simulations", headers=HEADERS)
    assert len(rv.json) == len(SIMULATIONS)
    assert rv.status_code == 200
