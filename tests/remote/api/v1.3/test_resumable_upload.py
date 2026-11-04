"""Tests for the resumable HTTP upload endpoint (/v1.3/upload/<target>)."""

import base64
import hashlib
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests
from conftest import HEADERS

from simdb.cli import resumable_upload as ru

INTEROP_HEADER = "Upload-Draft-Interop-Version"


def _digest(data):
    """RFC 9530 ``sha-256`` digest structured-field value for ``data``."""
    encoded = base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")
    return f"sha-256=:{encoded}:"


@pytest.fixture
def http_partition(client, tmp_path):
    """Point the ``http`` partition at a temporary directory for the test."""
    base = tmp_path / "http_staging"
    base.mkdir()
    client.application.simdb_config.set_option("partition.http", str(base))
    return base


def _patch(client, target, offset, data, complete, headers=None):
    h = dict(headers or HEADERS)
    h["Upload-Offset"] = str(offset)
    h["Upload-Complete"] = "?1" if complete else "?0"
    h["Content-Type"] = "application/partial-upload"
    return client.patch(f"/v1.3/upload/{target}", data=data, headers=h)


def test_upload_create_append_complete(client, http_partition):
    sim_hex = uuid.uuid4().hex
    target = f"{sim_hex}/sub/file.txt"

    # Create the upload resource (empty body).
    rv = client.post(
        f"/v1.3/upload/{target}",
        data=b"",
        headers={**HEADERS, "Upload-Complete": "?0", "Upload-Length": "11"},
    )
    assert rv.status_code == 201
    assert rv.headers["Upload-Offset"] == "0"
    assert rv.headers[INTEROP_HEADER] == "8"
    assert "Location" in rv.headers

    # First chunk.
    rv = _patch(client, target, 0, b"hello", complete=False)
    assert rv.status_code == 204
    assert rv.headers["Upload-Offset"] == "5"

    # HEAD reports current progress.
    rv = client.head(f"/v1.3/upload/{target}", headers=HEADERS)
    assert rv.status_code == 204
    assert rv.headers["Upload-Offset"] == "5"
    assert rv.headers["Upload-Complete"] == "?0"

    # Final chunk completes the upload.
    rv = _patch(client, target, 5, b" world", complete=True)
    assert rv.status_code == 200
    assert rv.headers["Upload-Offset"] == "11"
    assert rv.headers["Upload-Complete"] == "?1"

    final = http_partition / sim_hex / "sub" / "file.txt"
    assert final.read_bytes() == b"hello world"
    assert not (final.parent / (final.name + ".partial")).exists()


def test_upload_offset_mismatch_returns_409(client, http_partition):
    target = f"{uuid.uuid4().hex}/file.txt"
    client.post(
        f"/v1.3/upload/{target}", data=b"", headers={**HEADERS, "Upload-Complete": "?0"}
    )
    _patch(client, target, 0, b"abc", complete=False)

    # Wrong offset -> 409 with the server's actual offset.
    rv = _patch(client, target, 0, b"def", complete=False)
    assert rv.status_code == 409
    assert rv.headers["Upload-Offset"] == "3"


def test_upload_head_missing_returns_404(client, http_partition):
    rv = client.head(f"/v1.3/upload/{uuid.uuid4().hex}/missing.txt", headers=HEADERS)
    assert rv.status_code == 404


def test_upload_empty_file(client, http_partition):
    sim_hex = uuid.uuid4().hex
    target = f"{sim_hex}/empty.txt"
    client.post(
        f"/v1.3/upload/{target}", data=b"", headers={**HEADERS, "Upload-Complete": "?0"}
    )
    rv = _patch(client, target, 0, b"", complete=True)
    assert rv.status_code == 200
    assert (http_partition / sim_hex / "empty.txt").read_bytes() == b""


def test_upload_delete(client, http_partition):
    sim_hex = uuid.uuid4().hex
    target = f"{sim_hex}/file.txt"
    client.post(
        f"/v1.3/upload/{target}",
        data=b"data",
        headers={**HEADERS, "Upload-Complete": "?1"},
    )
    assert (http_partition / sim_hex / "file.txt").exists()

    rv = client.delete(f"/v1.3/upload/{target}", headers=HEADERS)
    assert rv.status_code == 204
    assert not (http_partition / sim_hex / "file.txt").exists()


def test_upload_path_traversal_rejected(client, http_partition):
    rv = client.post(
        "/v1.3/upload/..%2f..%2fescape.txt",
        data=b"x",
        headers={**HEADERS, "Upload-Complete": "?1"},
    )
    assert rv.status_code in (400, 403, 404)
    assert not (http_partition.parent / "escape.txt").exists()
    assert not Path("/tmp/escape.txt").exists()


class _Resp:
    """Adapt a Flask test-client response to the bits resumable_upload uses."""

    def __init__(self, rv):
        self.status_code = rv.status_code
        self.headers = rv.headers
        self.text = rv.get_data(as_text=True)


def _flask_transport(client, fail_once_at=None):
    """Route resumable_upload's ``requests`` calls to the Flask test client.

    @param fail_once_at: if set, raise ConnectionError the first time a PATCH is
        sent at this offset, to exercise the resume path.
    """
    state = {"failed": False}

    def _path(url):
        return urlsplit(url).path

    def head(url, headers=None, **kwargs):
        return _Resp(client.head(_path(url), headers=dict(headers or {}, **HEADERS)))

    def post(url, data=b"", headers=None, **kwargs):
        return _Resp(
            client.post(_path(url), data=data, headers=dict(headers or {}, **HEADERS))
        )

    def patch(url, data=b"", headers=None, **kwargs):
        offset = int((headers or {}).get("Upload-Offset", -1))
        if fail_once_at is not None and offset == fail_once_at and not state["failed"]:
            state["failed"] = True
            raise requests.ConnectionError("simulated network drop")
        return _Resp(
            client.patch(_path(url), data=data, headers=dict(headers or {}, **HEADERS))
        )

    return head, post, patch


def test_resumable_upload_client_against_server(client, http_partition, monkeypatch):
    head, post, patch = _flask_transport(client)
    monkeypatch.setattr(ru.requests, "head", head)
    monkeypatch.setattr(ru.requests, "post", post)
    monkeypatch.setattr(ru.requests, "patch", patch)

    sim_hex = uuid.uuid4().hex
    src = http_partition.parent / "source.bin"
    payload = b"0123456789" * 100  # 1000 bytes
    src.write_bytes(payload)

    ru.resumable_upload(
        f"http://localhost/v1.3/upload/{sim_hex}/source.bin", src, chunk_size=256
    )

    assert (http_partition / sim_hex / "source.bin").read_bytes() == payload


def test_resumable_upload_reports_progress(client, http_partition, monkeypatch):
    head, post, patch = _flask_transport(client)
    monkeypatch.setattr(ru.requests, "head", head)
    monkeypatch.setattr(ru.requests, "post", post)
    monkeypatch.setattr(ru.requests, "patch", patch)

    sim_hex = uuid.uuid4().hex
    src = http_partition.parent / "progress.bin"
    payload = b"y" * 1000
    src.write_bytes(payload)

    seen = []
    ru.resumable_upload(
        f"http://localhost/v1.3/upload/{sim_hex}/progress.bin",
        src,
        chunk_size=256,
        progress=seen.append,
    )

    # Progress is monotonic non-decreasing and reaches the full file size.
    assert seen == sorted(seen)
    assert seen[-1] == len(payload)


def test_resumable_upload_client_resumes_after_failure(
    client, http_partition, monkeypatch
):
    # Inject a connection drop at offset 256; the client should HEAD to recover
    # the server offset and continue rather than restart.
    head, post, patch = _flask_transport(client, fail_once_at=256)
    monkeypatch.setattr(ru.requests, "head", head)
    monkeypatch.setattr(ru.requests, "post", post)
    monkeypatch.setattr(ru.requests, "patch", patch)

    sim_hex = uuid.uuid4().hex
    src = http_partition.parent / "resume.bin"
    payload = bytes(range(256)) * 4  # 1024 bytes
    src.write_bytes(payload)

    ru.resumable_upload(
        f"http://localhost/v1.3/upload/{sim_hex}/resume.bin", src, chunk_size=256
    )

    assert (http_partition / sim_hex / "resume.bin").read_bytes() == payload


@pytest.fixture
def small_append_limit(client):
    """Advertise (and enforce) a tiny max-append-size for the duration of a test."""
    cfg = client.application.simdb_config
    cfg.set_option("server.max_append_size", "256")
    yield 256
    cfg.set_option("server.max_append_size", str(8 * 1024 * 1024))


def test_upload_advertises_and_enforces_append_limit(
    client, http_partition, small_append_limit
):
    target = f"{uuid.uuid4().hex}/file.bin"
    rv = client.post(
        f"/v1.3/upload/{target}", data=b"", headers={**HEADERS, "Upload-Complete": "?0"}
    )
    assert rv.status_code == 201
    assert rv.headers["Upload-Limit"] == "max-append-size=256"

    # A PATCH body larger than the advertised limit is rejected.
    rv = _patch(client, target, 0, b"x" * 300, complete=False)
    assert rv.status_code == 413


def test_client_respects_server_append_limit(
    client, http_partition, small_append_limit, monkeypatch
):
    head, post, patch = _flask_transport(client)
    monkeypatch.setattr(ru.requests, "head", head)
    monkeypatch.setattr(ru.requests, "post", post)
    monkeypatch.setattr(ru.requests, "patch", patch)

    sim_hex = uuid.uuid4().hex
    src = http_partition.parent / "big.bin"
    payload = b"z" * 1000  # larger than the 256-byte append limit
    src.write_bytes(payload)

    # Request a chunk size far larger than the server allows; the client must
    # clamp to the advertised max-append-size, so the upload still succeeds.
    ru.resumable_upload(
        f"http://localhost/v1.3/upload/{sim_hex}/big.bin", src, chunk_size=1_000_000
    )

    assert (http_partition / sim_hex / "big.bin").read_bytes() == payload


def test_resumable_upload_completes_multi_chunk(client, http_partition, monkeypatch):
    head, post, patch = _flask_transport(client)
    monkeypatch.setattr(ru.requests, "head", head)
    monkeypatch.setattr(ru.requests, "post", post)
    monkeypatch.setattr(ru.requests, "patch", patch)

    sim_hex = uuid.uuid4().hex
    src = http_partition.parent / "reuse.bin"
    payload = b"0123456789" * 100
    src.write_bytes(payload)

    # The file is uploaded across several chunks and assembled on the server.
    ru.resumable_upload(
        f"http://localhost/v1.3/upload/{sim_hex}/reuse.bin",
        src,
        chunk_size=256,
    )
    assert (http_partition / sim_hex / "reuse.bin").read_bytes() == payload


def test_patch_content_digest_match_accepted(client, http_partition):
    target = f"{uuid.uuid4().hex}/file.txt"
    client.post(
        f"/v1.3/upload/{target}", data=b"", headers={**HEADERS, "Upload-Complete": "?0"}
    )
    rv = _patch(
        client,
        target,
        0,
        b"hello",
        complete=False,
        headers={**HEADERS, "Content-Digest": _digest(b"hello")},
    )
    assert rv.status_code == 204
    assert rv.headers["Upload-Offset"] == "5"


def test_patch_content_digest_mismatch_rejected(client, http_partition):
    target = f"{uuid.uuid4().hex}/file.txt"
    client.post(
        f"/v1.3/upload/{target}", data=b"", headers={**HEADERS, "Upload-Complete": "?0"}
    )
    # Digest of different bytes than the body -> 400 and nothing appended.
    rv = _patch(
        client,
        target,
        0,
        b"hello",
        complete=False,
        headers={**HEADERS, "Content-Digest": _digest(b"goodbye")},
    )
    assert rv.status_code == 400
    assert rv.headers["Upload-Offset"] == "0"
    assert not (http_partition / target).exists()
    # The partial exists (created empty by POST) but the rejected body was not
    # appended.
    assert (http_partition / (target + ".partial")).read_bytes() == b""


def test_multi_chunk_upload_finalizes(client, http_partition):
    sim_hex = uuid.uuid4().hex
    target = f"{sim_hex}/file.txt"
    client.post(
        f"/v1.3/upload/{target}", data=b"", headers={**HEADERS, "Upload-Complete": "?0"}
    )
    _patch(
        client,
        target,
        0,
        b"hello",
        complete=False,
        headers={**HEADERS, "Content-Digest": _digest(b"hello")},
    )
    rv = _patch(
        client,
        target,
        5,
        b" world",
        complete=True,
        headers={**HEADERS, "Content-Digest": _digest(b" world")},
    )
    assert rv.status_code == 200
    assert (http_partition / sim_hex / "file.txt").read_bytes() == b"hello world"


def test_post_content_digest_mismatch_rejected(client, http_partition):
    sim_hex = uuid.uuid4().hex
    target = f"{sim_hex}/file.txt"
    rv = client.post(
        f"/v1.3/upload/{target}",
        data=b"hello",
        headers={**HEADERS, "Upload-Complete": "?0", "Content-Digest": _digest(b"x")},
    )
    assert rv.status_code == 400
    assert not (http_partition / sim_hex / "file.txt.partial").exists()


def test_unknown_digest_algorithm_ignored(client, http_partition):
    # A digest using an algorithm the server cannot recompute is ignored rather
    # than rejected, so the upload still succeeds.
    target = f"{uuid.uuid4().hex}/file.txt"
    client.post(
        f"/v1.3/upload/{target}", data=b"", headers={**HEADERS, "Upload-Complete": "?0"}
    )
    rv = _patch(
        client,
        target,
        0,
        b"hello",
        complete=False,
        headers={**HEADERS, "Content-Digest": "unixsum=:0061:"},
    )
    assert rv.status_code == 204
