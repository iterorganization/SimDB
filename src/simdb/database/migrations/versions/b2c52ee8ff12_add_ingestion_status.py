"""Add ingestion status

Revision ID: b2c52ee8ff12
Revises: 28bee3aa2429
Create Date: 2026-05-11 16:16:03.768893

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c52ee8ff12"
down_revision: Union[str, Sequence[str], None] = "28bee3aa2429"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        op.execute(
            "CREATE TYPE ingestionstatus AS ENUM ('QUEUED', 'COPYING', 'COPIED', "
            "'VALIDATING', 'VALIDATED', 'COMPLETED', 'COPY_FAILED', "
            "'VALIDATION_FAILED')"
        )
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "ingestion_status",
                sa.Enum(
                    "QUEUED",
                    "COPYING",
                    "COPIED",
                    "VALIDATING",
                    "VALIDATED",
                    "COMPLETED",
                    "COPY_FAILED",
                    "VALIDATION_FAILED",
                    name="ingestionstatus",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("ingestion_version", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE simulations SET ingestion_status = 'COMPLETED' WHERE ingestion_status "
        "IS NULL"
    )
    op.execute(
        "UPDATE simulations SET ingestion_version = 0 WHERE ingestion_version IS NULL"
    )
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.alter_column("ingestion_status", nullable=False)
        batch_op.alter_column("ingestion_version", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.drop_column("ingestion_version")
        batch_op.drop_column("ingestion_status")
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        op.execute("DROP TYPE ingestionstatus")
