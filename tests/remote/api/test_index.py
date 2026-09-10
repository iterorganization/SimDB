import pytest

from simdb.remote.apis import blueprints


@pytest.mark.parametrize("version", list(blueprints))
def test_versioned_index(client, version):
    """The versioned root must serve the index JSON, not flask-restx's 404 root."""
    rv = client.get(f"/{version}/")

    assert rv.status_code == 200
    assert rv.json["api"] == "simdb"
    # v1 reports "1.0" for blueprint key "v1", so only compare the prefix
    assert rv.json["api_version"].startswith(version.lstrip("v"))
    assert any(url.endswith("simulations") for url in rv.json["endpoints"])
