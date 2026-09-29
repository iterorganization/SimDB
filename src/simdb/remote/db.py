"""Construct the server's :class:`Database` from a SimDB configuration.

Shared by the Flask app and the ``simdb_migrate`` entry point so that both
resolve the same database from the same configuration.
"""

import threading
from pathlib import Path
from typing import Callable, Optional

import appdirs

from simdb.config import Config
from simdb.database import Database


def database_from_config(
    config: Config, scopefunc: Optional[Callable] = None
) -> Database:
    """
    Create the :class:`Database` described by the ``database`` config section.

    :param config: the loaded SimDB configuration.
    :param scopefunc: the session scope function to pass to the Database.
    :raises RuntimeError: if ``database.type`` is not a supported DBMS.
    """
    db_type = config.get_option("database.type")

    if db_type == "postgres":
        args = config.get_section("database")
        return Database(Database.DBMS.POSTGRESQL, scopefunc=scopefunc, **args)

    if db_type == "sqlite":
        file_option = config.get_string_option("database.file", default=None)
        if file_option:
            file = Path(file_option)
        else:
            file = Path(appdirs.user_data_dir("simdb"), "remote.db")
        file.parent.mkdir(parents=True, exist_ok=True)
        return Database(Database.DBMS.SQLITE, scopefunc=scopefunc, file=file)

    raise RuntimeError(f"Unknown database type in configuration: {db_type}.")


def request_scoped_database(config: Config) -> Database:
    """Create the Database used to serve requests, scoped per thread."""
    return database_from_config(config, scopefunc=lambda: threading.get_ident())
