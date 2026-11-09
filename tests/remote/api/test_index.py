import logging

import pytest

from simdb.config import Config
from simdb.remote.apis import blueprints
from simdb.remote.app import create_app


@pytest.mark.parametrize("version", list(blueprints))
def test_versioned_index(client, version):
    """The versioned root must serve the index JSON, not flask-restx's 404 root."""
    rv = client.get(f"/{version}/")

    assert rv.status_code == 200
    assert rv.json["api"] == "simdb"
    # v1 reports "1.0" for blueprint key "v1", so only compare the prefix
    assert rv.json["api_version"].startswith(version.lstrip("v"))
    assert any(url.endswith("simulations") for url in rv.json["endpoints"])


def test_authentication_error_logs_failure_notes(caplog, tmp_path):
    config = Config()
    config.load()
    config.set_option("database.type", "sqlite")
    config.set_option("database.file", str(tmp_path / "remote.db"))
    config.set_option("server.admin_password", "test123")
    config.set_option("server.upload_folder", str(tmp_path / "uploads"))
    config.set_option("authentication.type", "Firewall")
    config.set_option("authentication.firewall_user", "X-Forwarded-User")
    config.set_option("authentication.firewall_email", "X-Forwarded-Email")

    app = create_app(config=config, testing=True, debug=True)
    app.logger.setLevel(logging.DEBUG)

    with caplog.at_level(
        logging.DEBUG, logger=app.logger.name
    ), app.test_client() as client:
        response = client.get(
            "/v1.3/validation_schema",
            headers={
                "X-Forwarded-Email": "user@example.org",
                "X-Test-Header": "seen",
            },
        )

    assert response.status_code == 401
    assert "headers=[" in caplog.text
    assert "'Host'" in caplog.text
    assert "'X-Forwarded-Email'" in caplog.text
    assert "'X-Test-Header'" in caplog.text
    assert "notes=token authenticator: Invalid token" in caplog.text
    assert "firewall authenticator: Header X-Forwarded-User not found" in caplog.text
