from sqlalchemy import create_engine, inspect

from simdb.database.database import check_migrations, run_migrations


def test_migrations_initialize_outside_checkout(tmp_path, monkeypatch):
    """Alembic must locate its config and version scripts from the packaged
    migrations directory"""
    monkeypatch.chdir(tmp_path)
    engine = create_engine("sqlite:///:memory:")

    run_migrations(engine)

    assert check_migrations(engine)
    assert "simulations" in inspect(engine).get_table_names()
