import hashlib
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone

import pytest

from simdb.checksum import file_checksum, has_algorithm_prefix
from simdb.cli.manifest import DataType
from simdb.config import Config
from simdb.database import Database
from simdb.database.models import Base, File, OnlineMigrationHistory
from simdb.database.online_migrations import run_online_migrations
from simdb.imas.utils import SimDBUrl


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

    expected = file_checksum(uri)  # sha1:<hex>
    legacy = _add_file(db, uri, hashlib.sha1(b"hello world").hexdigest())
    already = _add_file(db, uri, expected)
    disabled = _add_file(db, uri, "")

    results = run_online_migrations(db, config=None)

    assert results["recalculate_checksums"] == 1
    db.session.refresh(legacy)
    assert legacy.checksum == expected
    assert has_algorithm_prefix(legacy.checksum)
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
    assert has_algorithm_prefix(file.checksum)
    assert "recalculate_checksums" in _applied(db)


def test_disabled_checksums_leave_stored_hashes_untouched(db, tmp_path):
    target = tmp_path / "data.txt"
    target.write_text("hello world")
    uri = SimDBUrl.build(scheme="file", path=target.as_posix())
    legacy_hex = hashlib.sha1(b"hello world").hexdigest()
    legacy = _add_file(db, uri, legacy_hex)

    config = Config()
    config.set_option("development.disable_checksum", True)
    results = run_online_migrations(db, config)

    assert results["recalculate_checksums"] == 0
    db.session.refresh(legacy)
    assert legacy.checksum == legacy_hex
    # Not recorded, so it still runs once checksums are enabled again.
    assert "recalculate_checksums" not in _applied(db)
    assert run_online_migrations(db, config=None)["recalculate_checksums"] == 1


def test_local_database_does_not_need_celery(tmp_path):
    """The client opens the local DB (and runs online migrations) without the
    server-only Celery dependency installed."""
    code = (
        "import builtins\n"
        "real = builtins.__import__\n"
        "def guard(name, *a, **k):\n"
        "    if name == 'celery' or name.startswith('celery.'):\n"
        "        raise ImportError('celery is a server-only dependency')\n"
        "    return real(name, *a, **k)\n"
        "builtins.__import__ = guard\n"
        "import sys\n"
        "from simdb.database import Database\n"
        "from simdb.database.database import _run_online_migrations\n"
        "from simdb.database.models import Base\n"
        "db = Database(Database.DBMS.SQLITE, file=sys.argv[1])\n"
        "Base.metadata.create_all(db.engine)\n"
        "_run_online_migrations(db, None)\n"
        "import simdb.cli.simdb\n"
    )
    subprocess.run([sys.executable, "-c", code, str(tmp_path / "sim.db")], check=True)
