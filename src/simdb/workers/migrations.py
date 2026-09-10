"""Online (data) migrations.

Unlike Alembic migrations, which change the database *schema* offline, these
migrations transform live *data* while the system is online. They are run
automatically:

* on the server, by :func:`simdb.workers.tasks.run_online_migrations_task`
  which is queued when a Celery worker starts;
* for the local SQLite database, by ``get_local_db`` after the schema is
  brought up to date.

Which migrations have run is tracked in the ``online_migrations`` table (see
:class:`simdb.database.models.OnlineMigrationHistory`): a migration is recorded
once it completes successfully and is skipped on subsequent runs. A migration
that only partially completes (e.g. a file was temporarily unavailable) is not
recorded, so it is retried on the next run -- migrations must therefore be
idempotent.

To add a migration, write a function ``def my_migration(database, config) ->
MigrationResult`` and append an :class:`OnlineMigration` to
:data:`ONLINE_MIGRATIONS` with a unique, stable ``name``.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Set

from simdb.config import Config
from simdb.database.database import Database
from simdb.database.models import File, OnlineMigrationHistory

logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    """Outcome of a single online migration run.

    :param changed: number of rows changed during this run.
    :param complete: whether the migration finished with nothing left to do.
        When ``False`` the migration is not recorded and will run again.
    """

    changed: int
    complete: bool = True


@dataclass(frozen=True)
class OnlineMigration:
    """A single idempotent data migration."""

    name: str
    run: Callable[[Database, Config], MigrationResult]


def _recalculate_checksums(database: Database, config: Config) -> MigrationResult:
    """Recalculate and prefix checksums that predate the ``sha1:`` format.

    Any file whose stored checksum lacks an ``<algorithm>:`` prefix is
    re-hashed from disk (picking up the platform-independent, sorted-glob
    computation) and stored in the new ``sha1:<hex>`` form. Files that cannot be
    hashed right now are left unchanged and reported as incomplete so the
    migration is retried later.
    """
    # Only files whose checksum lacks an "<algorithm>:" prefix still need
    # migrating. Empty checksums (checksum generation disabled) are left alone.
    unmigrated = (
        database.session.query(File)
        .filter(File.checksum.isnot(None))
        .filter(File.checksum != "")
        .filter(File.checksum.notlike("%:%"))
        .all()
    )

    updated = 0
    failed = 0
    for file in unmigrated:
        try:
            file.checksum = file.generate_checksum(config, [])
        except Exception:
            failed += 1
            logger.exception(
                "Could not recalculate checksum for file %s; leaving it unchanged",
                file.uri,
            )
            continue
        updated += 1
    if updated:
        database.session.commit()
    if failed:
        logger.warning(
            "Checksum recalculation left %d file(s) unmigrated (see errors above); "
            "they will be retried on the next run",
            failed,
        )
    return MigrationResult(changed=updated, complete=(failed == 0))


ONLINE_MIGRATIONS = [
    OnlineMigration(name="recalculate_checksums", run=_recalculate_checksums),
]


def _applied_migration_names(database: Database) -> Set[str]:
    return {row[0] for row in database.session.query(OnlineMigrationHistory.name).all()}


def _record_migration(database: Database, name: str) -> None:
    database.session.add(OnlineMigrationHistory(name=name, applied_at=datetime.now()))
    database.session.commit()


def run_online_migrations(database: Database, config: Config) -> Dict[str, int]:
    """Run every not-yet-applied online migration in order.

    :return: a mapping of migration name to rows changed, for migrations that
        actually ran this time (already-applied migrations are omitted).
    """
    applied = _applied_migration_names(database)
    results: Dict[str, int] = {}
    for migration in ONLINE_MIGRATIONS:
        if migration.name in applied:
            continue
        result = migration.run(database, config)
        results[migration.name] = result.changed
        if result.complete:
            _record_migration(database, migration.name)
            logger.info(
                "Online migration %r applied (%d row(s) changed)",
                migration.name,
                result.changed,
            )
        else:
            logger.warning(
                "Online migration %r did not fully complete (%d row(s) changed); "
                "it will run again next time",
                migration.name,
                result.changed,
            )
    return results
