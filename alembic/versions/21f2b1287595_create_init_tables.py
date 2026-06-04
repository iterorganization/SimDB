"""create init tables

Revision ID: 21f2b1287595
Revises:
Create Date: 2026-02-13 10:11:39.262884

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from simdb.database.models.types import URI, UUID, ChoiceType
from simdb.notifications import Notification

# revision identifiers, used by Alembic.
revision: str = "21f2b1287595"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define notification choices
NOTIFICATION_CHOICES = {
    Notification.VALIDATION: "V",
    Notification.REVISION: "R",
    Notification.OBSOLESCENCE: "O",
    Notification.ALL: "A",
}


def upgrade() -> None:
    """Upgrade schema."""
    # Get connection to inspect existing database schema
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create files table if it doesn't exist
    if "files" not in existing_tables:
        op.create_table(
            "files",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("uuid", UUID(), nullable=False),
            sa.Column("usage", sa.String(length=250), nullable=True),
            sa.Column("uri", URI(length=1024), nullable=True),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.Column(
                "type",
                sa.Enum("UNKNOWN", "UUID", "FILE", "IMAS", "UDA", name="type"),
                nullable=True,
            ),
            sa.Column("purpose", sa.String(length=250), nullable=True),
            sa.Column("sensitivity", sa.String(length=20), nullable=True),
            sa.Column("access", sa.String(length=20), nullable=True),
            sa.Column("embargo", sa.String(length=20), nullable=True),
            sa.Column("datetime", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_files_uuid"), "files", ["uuid"], unique=True)

    # Create simulations table if it doesn't exist
    if "simulations" not in existing_tables:
        op.create_table(
            "simulations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("uuid", UUID(), nullable=False),
            sa.Column("alias", sa.String(length=250), nullable=True),
            sa.Column("datetime", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_simulations_alias"), "simulations", ["alias"], unique=True
        )
        op.create_index(
            op.f("ix_simulations_uuid"), "simulations", ["uuid"], unique=True
        )

    # Create watchers table if it doesn't exist
    if "watchers" not in existing_tables:
        op.create_table(
            "watchers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=250), nullable=True),
            sa.Column("email", sa.String(length=1000), nullable=True),
            sa.Column(
                "notification",
                ChoiceType(
                    choices=NOTIFICATION_CHOICES, length=1, enum_type=Notification
                ),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create metadata table if it doesn't exist
    if "metadata" not in existing_tables:
        op.create_table(
            "metadata",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("sim_id", sa.Integer(), nullable=True),
            sa.Column("element", sa.String(length=250), nullable=False),
            sa.Column("value", sa.PickleType(), nullable=True),
            sa.ForeignKeyConstraint(
                ["sim_id"],
                ["simulations.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_metadata_sim_id"), "metadata", ["sim_id"], unique=False
        )
        op.create_index(
            "metadata_index", "metadata", ["sim_id", "element"], unique=True
        )

    # Create simulation_input_files table if it doesn't exist
    if "simulation_input_files" not in existing_tables:
        op.create_table(
            "simulation_input_files",
            sa.Column("simulation_id", sa.Integer(), nullable=True),
            sa.Column("file_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["file_id"],
                ["files.id"],
            ),
            sa.ForeignKeyConstraint(
                ["simulation_id"],
                ["simulations.id"],
            ),
        )

    # Create simulation_output_files table if it doesn't exist
    if "simulation_output_files" not in existing_tables:
        op.create_table(
            "simulation_output_files",
            sa.Column("simulation_id", sa.Integer(), nullable=True),
            sa.Column("file_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["file_id"],
                ["files.id"],
            ),
            sa.ForeignKeyConstraint(
                ["simulation_id"],
                ["simulations.id"],
            ),
        )

    # Create simulation_watchers table if it doesn't exist
    if "simulation_watchers" not in existing_tables:
        op.create_table(
            "simulation_watchers",
            sa.Column("simulation_id", sa.Integer(), nullable=True),
            sa.Column("watcher_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["simulation_id"],
                ["simulations.id"],
            ),
            sa.ForeignKeyConstraint(
                ["watcher_id"],
                ["watchers.id"],
            ),
        )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("simulation_watchers")
    op.drop_table("simulation_output_files")
    op.drop_table("simulation_input_files")
    op.drop_index("metadata_index", table_name="metadata")
    op.drop_index(op.f("ix_metadata_sim_id"), table_name="metadata")
    op.drop_table("metadata")
    op.drop_table("watchers")
    op.drop_index(op.f("ix_simulations_uuid"), table_name="simulations")
    op.drop_index(op.f("ix_simulations_alias"), table_name="simulations")
    op.drop_table("simulations")
    op.drop_index(op.f("ix_files_uuid"), table_name="files")
    op.drop_table("files")
    # ### end Alembic commands ###
