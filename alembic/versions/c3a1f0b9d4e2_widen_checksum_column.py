"""Widen files.checksum column for algorithm-prefixed checksums

Checksums are now stored as ``<algorithm>:<hexdigest>`` (e.g. ``sha1:...``).
Widen the column from 64 to 128 characters so the prefix fits today and leaves
room for longer digests (e.g. ``sha256:``) in the future.

The actual re-hashing of existing values is done by the online (data) migration
``recalculate_checksums`` in :mod:`simdb.workers.migrations`, not here.

Revision ID: c3a1f0b9d4e2
Revises: 6fb9b8fbac38
Create Date: 2026-07-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a1f0b9d4e2"
down_revision: Union[str, Sequence[str], None] = "6fb9b8fbac38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.alter_column(
            "checksum",
            existing_type=sa.String(length=64),
            type_=sa.String(length=128),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.alter_column(
            "checksum",
            existing_type=sa.String(length=128),
            type_=sa.String(length=64),
            existing_nullable=True,
        )
