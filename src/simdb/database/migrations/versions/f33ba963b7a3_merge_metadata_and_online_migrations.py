"""merge metadata and online migrations

Revision ID: f33ba963b7a3
Revises: a3f1c7d94e02, d4b2e6f1a7c3
Create Date: 2026-10-13 17:06:30.841679

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "f33ba963b7a3"
down_revision: Union[str, Sequence[str], None] = ("a3f1c7d94e02", "d4b2e6f1a7c3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
