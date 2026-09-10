import hashlib
import tempfile
import uuid
from datetime import datetime, timezone

import pytest

from simdb.checksum import is_prefixed, sha1_checksum
from simdb.cli.manifest import DataType
from simdb.database import Database
from simdb.database.models import Base, File, OnlineMigrationHistory
from simdb.imas.utils import SimDBUrl
from simdb.workers.migrations import run_online_migrations


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_file = f.name
    database = Database(Database.DBMS.SQLITE, file=db_file)
    Base.metadata.create_all(database.engine)
    yield database
    database.close()


def _add_file(db, uri: SimDBUrl, checksum: str) -> File:
    file = File(DataType.FILE, uri, perform_integrity_check=False)
    file.uuid = uuid.uuid1()
    file.checksum = checksum
    file.datetime = datetime.now(timezone.utc)
    db.session.add(file)
    db.session.commit()
    return file


def _applied(db):
    return {m.name for m in db.session.query(OnlineMigrationHistory).all()}


def test_recalculates_and_prefixes_legacy_checksums(db, tmp_path):
    target = tmp_path / "data.txt"
    target.write_text("hello world")
    uri = SimDBUrl.build(scheme="file", path=target.as_posix())

    expected = sha1_checksum(uri)  # sha1:<hex>
    legacy = _add_file(db, uri, hashlib.sha1(b"hello world").hexdigest())
    already = _add_file(db, uri, expected)
    disabled = _add_file(db, uri, "")

    results = run_online_migrations(db, config=None)

    assert results["recalculate_checksums"] == 1
    db.session.refresh(legacy)
    assert legacy.checksum == expected
    assert is_prefixed(legacy.checksum)
    assert already.checksum == expected  # untouched
    assert disabled.checksum == ""  # untouched
    assert "recalculate_checksums" in _applied(db)


def test_completed_migration_is_recorded_and_skipped(db, tmp_path):
    target = tmp_path / "data.txt"
    target.write_text("content")
    uri = SimDBUrl.build(scheme="file", path=target.as_posix())
    _add_file(db, uri, hashlib.sha1(b"content").hexdigest())

    first = run_online_migrations(db, config=None)
    assert first["recalculate_checksums"] == 1
    assert "recalculate_checksums" in _applied(db)

    # Already recorded -> not run again (omitted from the results mapping).
    second = run_online_migrations(db, config=None)
    assert "recalculate_checksums" not in second


def test_incomplete_migration_is_not_recorded_and_retries(db, tmp_path):
    # File points at a path that does not exist, so it cannot be hashed.
    missing_uri = SimDBUrl.build(scheme="file", path=str(tmp_path / "gone.txt"))
    file = _add_file(db, missing_uri, "deadbeef")

    results = run_online_migrations(db, config=None)
    assert results["recalculate_checksums"] == 0
    assert file.checksum == "deadbeef"  # left for retry
    assert "recalculate_checksums" not in _applied(db)

    # Once the file becomes available, a later run migrates it and records it.
    (tmp_path / "gone.txt").write_text("now here")
    results = run_online_migrations(db, config=None)
    assert results["recalculate_checksums"] == 1
    assert is_prefixed(file.checksum)
    assert "recalculate_checksums" in _applied(db)
