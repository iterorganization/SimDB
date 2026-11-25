import contextlib
import pytest
from unittest import mock
from simdb.database import Database
from simdb.database.database import DatabaseError


@mock.patch("sqlalchemy.create_engine")
def test_create_sqlite_database(create_engine):
    db = Database(Database.DBMS.SQLITE, file="simdb.db")
    create_engine.assert_called_once_with("sqlite:///simdb.db")
    assert db.engine == create_engine.return_value


def test_create_sqlite_database_with_missing_parameters():
    with pytest.raises(ValueError, match=".* parameter .*"):
        Database(Database.DBMS.SQLITE)


@mock.patch("sqlalchemy.create_engine")
def test_create_postrges_database(create_engine):
    db = Database(Database.DBMS.POSTGRESQL, host="test.server.com", port=5432)

    create_engine.assert_called_once_with(
        "postgresql+psycopg2://simdb:simdb@test.server.com:5432/simdb",
        pool_size=25,
        max_overflow=50,
        pool_pre_ping=True,
        pool_recycle=3600
    )
    assert db.engine == create_engine.return_value


def test_create_postgres_database_with_missing_parameters():
    with pytest.raises(ValueError, match=".* port .*"):
        Database(Database.DBMS.POSTGRESQL, host="test")
    with pytest.raises(ValueError, match=".* host .*"):
        Database(Database.DBMS.POSTGRESQL, port=5432)


@mock.patch("sqlalchemy.create_engine")
def test_create_mssql_database(create_engine):
    db = Database(Database.DBMS.MSSQL, user="simdb", password="test", dsnname="simdb")
    create_engine.assert_called_once_with("mssql+pyodbc://simdb:test@simdb")
    assert db.engine == create_engine.return_value


def test_create_mssql_database_with_missing_parameters():
    with pytest.raises(ValueError, match=".* user .*"):
        Database(Database.DBMS.MSSQL, password="test", dsnname="simdb")
    with pytest.raises(ValueError, match=".* password .*"):
        Database(Database.DBMS.MSSQL, user="simdb", dsnname="simdb")
    with pytest.raises(ValueError, match=".* dsnname .*"):
        Database(Database.DBMS.MSSQL, user="simdb", password="test")


def _make_db_migrated_by_newer_client(path, revision):
    import sqlite3

    with contextlib.closing(sqlite3.connect(path)) as con:
        con.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        con.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
        con.commit()


def test_sqlite_database_migrated_by_newer_client_advises_upgrade(tmp_path):
    db_file = tmp_path / "sim.db"
    _make_db_migrated_by_newer_client(db_file, "f33ba963b7a3")

    with pytest.raises(DatabaseError) as excinfo:
        Database(Database.DBMS.SQLITE, file=str(db_file))

    message = str(excinfo.value)
    assert str(db_file) in message
    assert "f33ba963b7a3" in message
    assert "pip install --upgrade imas-simdb" in message


def test_new_sqlite_database_is_created(tmp_path):
    db_file = tmp_path / "sim.db"

    db = Database(Database.DBMS.SQLITE, file=str(db_file))
    try:
        assert db.list_simulations() == []
    finally:
        db.close()
