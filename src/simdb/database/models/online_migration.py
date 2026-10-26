from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import types as sql_types

from .base import Base


class OnlineMigrationHistory(Base):
    """Record of an applied online (data) migration.

    Online migrations transform live data (see :mod:`simdb.workers.migrations`).
    One row is written per migration once it has completed successfully, which
    lets the runner skip migrations that have already run.
    """

    __tablename__ = "online_migrations"
    name = Column(sql_types.String(255), primary_key=True)
    applied_at = Column(sql_types.DateTime, nullable=False, default=datetime.now)

    def __init__(self, name: str, applied_at: datetime) -> None:
        self.name = name
        self.applied_at = applied_at

    def __str__(self) -> str:
        return f"{self.name} (applied {self.applied_at})"
