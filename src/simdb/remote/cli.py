"""Command line entry points for administering a SimDB server."""

import os
import sys

from simdb.config import Config
from simdb.database.database import run_migrations

from .db import database_from_config


def migrate() -> None:
    """
    Apply any pending database migrations, then exit.

    Reads the same configuration as the server, so the database does not have to
    be identified a second time. The migration scripts ship inside the installed
    package, so no Alembic checkout is required.
    """
    config = Config(os.environ.get("SIMDB_CONFIG_FILE", default="app.cfg"))
    config.load()

    database = database_from_config(config)
    try:
        run_migrations(database.engine)
    finally:
        database.remove()

    print("Database migrated to the latest revision.", file=sys.stderr)
