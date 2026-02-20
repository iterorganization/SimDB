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
    if not has_flask:
        pytest.skip("Flask not installed")
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
    config.set_option("role.admin.users", "admin,admin2")
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


@pytest.fixture(scope="session")
def client_copy_files():
    if not has_flask:
        pytest.skip("Flask not installed")
    config = Config()
    config.load()
    db_fd, db_file = tempfile.mkstemp()
    upload_dir = tempfile.mkdtemp()
    config.set_option("database.type", "sqlite")
    config.set_option("database.file", db_file)
    config.set_option("server.admin_password", TEST_PASSWORD)
    config.set_option("server.upload_folder", upload_dir)
    config.set_option("authentication.type", "None")
    config.set_option("server.copy_files", True)
    config.set_option("role.admin.users", "admin,admin2")
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
    add_watcher=False, uploaded_by=None, alias=None, **overrides
) -> SimulationPostData:
    if alias is None:
        alias = uuid.uuid4().hex
    simulation_data = SimulationData(alias=alias, **overrides)
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


def post_simulation(client, simulation_data, headers=HEADERS):
    rv_post = client.post(
        "/v1.2/simulations",
        json=simulation_data.model_dump(mode="json"),
        headers=headers,
        content_type="application/json",
    )
    return rv_post
