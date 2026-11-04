"""Make watcher email not nullable

Revision ID: 9e9a4a7cd639
Revises: 21f2b1287595
Create Date: 2026-02-18 16:48:17.152617

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e9a4a7cd639"
down_revision: Union[str, Sequence[str], None] = "21f2b1287595"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Delete rows with NULL emails, a watcher without email is invalid data
    op.execute("DELETE FROM watchers WHERE email IS NULL")

    with op.batch_alter_table("watchers", schema=None) as batch_op:
        batch_op.alter_column(
            "email", existing_type=sa.VARCHAR(length=1000), nullable=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("watchers", schema=None) as batch_op:
        batch_op.alter_column(
            "email", existing_type=sa.VARCHAR(length=1000), nullable=True
        )
