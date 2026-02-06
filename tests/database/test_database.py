from unittest import mock

import pytest

from simdb.database import Database


@mock.patch("sqlalchemy.create_engine")
def test_create_sqlite_database(create_engine):
    db = Database(Database.DBMS.SQLITE, file="simdb.db")
    create_engine.assert_called_once_with("sqlite:///simdb.db")
    assert db.engine == create_engine.return_value


def test_create_sqlite_database_with_missing_parameters():
    with pytest.raises(ValueError, match=r".* parameter .*"):
        Database(Database.DBMS.SQLITE)


@mock.patch("sqlalchemy.create_engine")
def test_create_postrges_database(create_engine):
    db = Database(Database.DBMS.POSTGRESQL, host="test.server.com", port=5432)

    create_engine.assert_called_once_with(
        "postgresql+psycopg2://simdb:simdb@test.server.com:5432/simdb",
        pool_size=25,
        max_overflow=50,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    assert db.engine == create_engine.return_value


def test_create_postgres_database_with_missing_parameters():
    with pytest.raises(ValueError, match=r".* port .*"):
        Database(Database.DBMS.POSTGRESQL, host="test")
    with pytest.raises(ValueError, match=r".* host .*"):
        Database(Database.DBMS.POSTGRESQL, port=5432)


@mock.patch("sqlalchemy.create_engine")
def test_create_mssql_database(create_engine):
    db = Database(Database.DBMS.MSSQL, user="simdb", password="test", dsnname="simdb")
    create_engine.assert_called_once_with("mssql+pyodbc://simdb:test@simdb")
    assert db.engine == create_engine.return_value


def test_create_mssql_database_with_missing_parameters():
    with pytest.raises(ValueError, match=r".* user .*"):
        Database(Database.DBMS.MSSQL, password="test", dsnname="simdb")
    with pytest.raises(ValueError, match=r".* password .*"):
        Database(Database.DBMS.MSSQL, user="simdb", dsnname="simdb")
    with pytest.raises(ValueError, match=r".* dsnname .*"):
        Database(Database.DBMS.MSSQL, user="simdb", password="test")
