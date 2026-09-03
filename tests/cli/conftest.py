"""Shared fixtures for the ``simdb`` command line interface tests.

Every test here drives the CLI through :class:`click.testing.CliRunner`, so the
fixtures below take care of the two things that would otherwise leak between
tests and into the developer's machine: the configuration that the CLI reads at
startup, and the handshake :class:`~simdb.cli.remote_api.RemoteAPI` performs
against a remote when it is constructed.
"""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from click.testing import CliRunner, Result

from simdb.cli.remote_api import RemoteAPI
from simdb.cli.simdb import cli

REMOTE_NAME = "test"
REMOTE_URL = "http://0.0.0.0:5000/"
REMOTE_TOKEN = "123ABC"

SERVER_ENDPOINTS = ["v1", "v1.1", "v1.1.1", "v1.2", "v1.3"]
"""API versions the fake remote advertises."""


@pytest.fixture(autouse=True)
def isolated_config_environment(tmp_path, monkeypatch):
    """Point the CLI at throw-away site and user configuration files.

    :class:`~simdb.config.config.Config` reads ``simdb.cfg`` from the platform
    config directories unless ``SIMDB_SITE_CONFIG_PATH``/
    ``SIMDB_USER_CONFIG_PATH`` say otherwise. Without this fixture the outcome of
    a test depends on whether the machine running it happens to have a real
    SimDB configuration, which is exactly the kind of difference that makes a
    suite pass locally and fail in CI.
    """
    for variable in [name for name in os.environ if name.startswith("SIMDB_")]:
        monkeypatch.delenv(variable)
    monkeypatch.setenv("SIMDB_SITE_CONFIG_PATH", str(tmp_path / "site-simdb.cfg"))
    monkeypatch.setenv("SIMDB_USER_CONFIG_PATH", str(tmp_path / "user-simdb.cfg"))


@pytest.fixture
def config_file(tmp_path) -> Path:
    """A configuration file declaring a single, default, token-authenticated remote."""
    config_path = tmp_path / "simdb.cfg"
    config_path.write_text(
        f'[remote "{REMOTE_NAME}"]\n'
        f"url = {REMOTE_URL}\n"
        "default = True\n"
        f"token = {REMOTE_TOKEN}\n"
        "\n"
        "[db]\n"
        # Keep any command that reaches the real database away from the local
        # one in the user's data directory.
        f"file = {tmp_path / 'sim.db'}\n"
    )
    return config_path


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def invoke(runner, config_file):
    """Invoke the ``simdb`` CLI against the throw-away :func:`config_file`.

    ``invoke("simulation", "list")`` runs ``simdb --config-file=... simulation
    list``. Any keyword argument is forwarded to
    :meth:`click.testing.CliRunner.invoke`, so ``input=`` can be used to answer
    prompts.
    """

    def _invoke(*args: str, **kwargs) -> Result:
        return runner.invoke(cli, [f"--config-file={config_file}", *args], **kwargs)

    return _invoke


@pytest.fixture
def remote_handshake():
    """Stub the requests :class:`RemoteAPI` makes while it is being constructed.

    ``RemoteAPI.__init__`` asks the remote for its authentication scheme, its
    endpoints, and its versions before any command specific request is made.
    Tests that only care about the command itself get all four stubbed here, and
    can still assert on them through the returned namespace::

        def test_something(invoke, remote_handshake):
            ...
            assert remote_handshake.get_api_version.called
    """
    with mock.patch.object(
        RemoteAPI, "get_server_authentication", return_value="None"
    ) as get_server_authentication, mock.patch.object(
        RemoteAPI, "get_endpoints", return_value=list(SERVER_ENDPOINTS)
    ) as get_endpoints, mock.patch.object(
        RemoteAPI, "get_api_version", return_value="1.3"
    ) as get_api_version, mock.patch.object(
        RemoteAPI, "get_server_version", return_value="0.11"
    ) as get_server_version:
        yield SimpleNamespace(
            get_server_authentication=get_server_authentication,
            get_endpoints=get_endpoints,
            get_api_version=get_api_version,
            get_server_version=get_server_version,
        )


@pytest.fixture
def local_db():
    """Replace the local database with a mock in every module that looks it up.

    ``get_local_db`` is imported into each command module, so patching a single
    import site silently leaves the other commands talking to the real database
    in the user's data directory.
    """
    db = mock.Mock()
    with mock.patch(
        "simdb.cli.commands.alias.get_local_db", return_value=db
    ), mock.patch("simdb.cli.commands.simulation.get_local_db", return_value=db):
        yield db


@pytest.fixture
def data_file(tmp_path) -> Path:
    """A small file a manifest can reference as an input or output."""
    path = tmp_path / "data.txt"
    path.write_text("simulation data\n")
    return path


@pytest.fixture
def manifest_file(tmp_path, data_file) -> Path:
    """A minimal, valid manifest referencing only local files."""
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        f"""\
manifest_version: 2
alias: simulation-alias

inputs:
  - uri: file://{data_file}

outputs:
  - uri: file://{data_file}

metadata:
- values:
    workflow:
      name: Workflow Name
      git: ssh://git@git.iter.org/wf/workflow.git
      branch: master
      commit: 079e84d5ae8a0eec6dcf3819c98f3c05f48e952f
"""
    )
    return manifest_path
