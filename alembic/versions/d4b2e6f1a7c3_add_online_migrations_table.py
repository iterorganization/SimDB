"""Add online_migrations tracking table

Records which online (data) migrations have been applied, so the runner in
:mod:`simdb.workers.migrations` can skip migrations that have already run.

Revision ID: d4b2e6f1a7c3
Revises: c3a1f0b9d4e2
Create Date: 2026-07-17 00:00:01.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4b2e6f1a7c3"
down_revision: Union[str, Sequence[str], None] = "c3a1f0b9d4e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "online_migrations",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("online_migrations")
