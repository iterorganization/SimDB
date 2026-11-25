from unittest import mock

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from simdb.database.database import (
    Confirm,
    DatabaseOutdatedError,
    DatabaseTooNewError,
    _alembic_config,
    check_migrations,
    get_local_db,
    run_migrations,
)


def test_migrations_initialize_outside_checkout(tmp_path, monkeypatch):
    """Alembic must locate its config and version scripts from the packaged
    migrations directory"""
    monkeypatch.chdir(tmp_path)
    engine = create_engine("sqlite:///:memory:")

    run_migrations(engine)

    assert check_migrations(engine)
    assert "simulations" in inspect(engine).get_table_names()


UNKNOWN_REVISION = "from_newer_simdb"


def _migrated_engine(db_file, revision=None):
    """A database migrated to head, then optionally stamped with ``revision``."""
    engine = create_engine(f"sqlite:///{db_file}")
    run_migrations(engine)
    if revision is not None:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE alembic_version SET version_num = :rev"), {"rev": revision}
            )
    return engine


def _local_config(db_file):
    config = mock.Mock()
    config.get_string_option.side_effect = lambda key, default=None: (
        str(db_file) if key == "db.file" else default
    )
    return config


def test_check_migrations_rejects_a_revision_from_a_newer_simdb(tmp_path):
    engine = _migrated_engine(tmp_path / "sim.db", UNKNOWN_REVISION)

    with pytest.raises(DatabaseTooNewError, match="newer version of SimDB"):
        check_migrations(engine)


def test_check_migrations_still_reports_an_older_revision_as_outdated(tmp_path):
    base = ScriptDirectory.from_config(_alembic_config()).get_base()
    engine = _migrated_engine(tmp_path / "sim.db", base)

    with pytest.raises(DatabaseOutdatedError):
        check_migrations(engine)


@mock.patch.object(Confirm, "ask")
def test_local_db_from_a_newer_simdb_explains_how_to_recover(ask, tmp_path):
    """#120: downgrading the client must not offer to migrate (and then crash)."""
    db_file = tmp_path / "sim.db"
    _migrated_engine(db_file, UNKNOWN_REVISION).dispose()

    with pytest.raises(DatabaseTooNewError) as excinfo:
        get_local_db(_local_config(db_file))

    assert not ask.called
    assert not (tmp_path / "backups").exists()
    message = str(excinfo.value)
    assert "newer version of SimDB" in message
    assert str(db_file) in message
    assert str(tmp_path / "backups") in message
