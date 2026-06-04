"""convert_metadata_to_json_column

Revision ID: 28bee3aa2429
Revises: 9e9a4a7cd639
Create Date: 2026-02-26 17:01:30.925750

"""

import json
import pickle
from typing import Any, Sequence, Union

import numpy as np
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "28bee3aa2429"
down_revision: Union[str, Sequence[str], None] = "9e9a4a7cd639"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _make_json_serializable(value: Any) -> Any:
    """Recursively convert a value to something JSON-serializable.

    Numpy arrays are converted to Range dicts using their min and max values.
    """
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, float)) and np.isfinite(value):
        return value
    if isinstance(value, (list, tuple)):
        return _make_json_serializable(np.array(value))
    if isinstance(value, dict):
        return {str(k): _make_json_serializable(v) for k, v in value.items()}
    # Convert numpy arrays to Range format
    try:
        if isinstance(value, np.ndarray) and value.size > 0:
            return {
                "min": _make_json_serializable(value.min()),
                "max": _make_json_serializable(value.max()),
            }
    except ImportError:
        pass
    return str(value)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Add metadata column only if it doesn't already exist (e.g. created via create_all)
    existing_columns = [col["name"] for col in inspector.get_columns("simulations")]
    if "metadata" not in existing_columns:
        if conn.dialect.name == "postgresql":
            op.add_column(
                "simulations",
                sa.Column(
                    "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
                ),
            )
        else:
            op.add_column(
                "simulations", sa.Column("metadata", sa.JSON(), nullable=True)
            )

    # Migrate existing data from metadata table if it still exists
    if "metadata" in inspector.get_table_names():
        result = conn.execute(text("SELECT DISTINCT sim_id FROM metadata"))
        sim_ids = [row[0] for row in result]

        for sim_id in sim_ids:
            meta_rows = conn.execute(
                text("SELECT element, value FROM metadata WHERE sim_id = :sim_id"),
                {"sim_id": sim_id},
            )

            meta_dict = {}
            for element, value in meta_rows:
                if value is not None:
                    try:
                        unpickled = (
                            pickle.loads(value)
                            if isinstance(value, (bytes, bytearray, memoryview))
                            else value
                        )
                    except Exception:
                        unpickled = repr(value)
                    meta_dict[element] = _make_json_serializable(unpickled)
                else:
                    meta_dict[element] = None

            if conn.dialect.name == "postgresql":
                conn.execute(
                    text(
                        "UPDATE simulations SET metadata = :metadata WHERE id = :sim_id"
                    ),
                    {"metadata": json.dumps(meta_dict), "sim_id": sim_id},
                )
            else:
                conn.execute(
                    text(
                        "UPDATE simulations SET metadata = :metadata WHERE id = :sim_id"
                    ),
                    {"metadata": json.dumps(meta_dict), "sim_id": sim_id},
                )

        op.drop_index("metadata_index", table_name="metadata")
        op.drop_index(op.f("ix_metadata_sim_id"), table_name="metadata")
        op.drop_table("metadata")


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()

    # Recreate metadata table
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
    op.create_index(op.f("ix_metadata_sim_id"), "metadata", ["sim_id"], unique=False)
    op.create_index("metadata_index", "metadata", ["sim_id", "element"], unique=True)

    # Migrate data back from JSON column to metadata table
    if conn.dialect.name == "postgresql":
        migration_query = text("""
            INSERT INTO metadata (sim_id, element, value)
            SELECT s.id, kv.key, kv.value::text
            FROM simulations s, json_each_text(s.metadata::json) kv
            WHERE s.metadata IS NOT NULL
        """)
        conn.execute(migration_query)
    else:
        result = conn.execute(
            text("SELECT id, metadata FROM simulations WHERE metadata IS NOT NULL")
        )
        for sim_id, metadata_json in result:
            if metadata_json:
                try:
                    meta_dict = json.loads(metadata_json)
                    for element, value in meta_dict.items():
                        # Pickle the value for storage
                        pickled_value = pickle.dumps(value, 0)
                        conn.execute(
                            text(
                                "INSERT INTO metadata (sim_id, element, value) "
                                "VALUES (:sim_id, :element, :value)"
                            ),
                            {
                                "sim_id": sim_id,
                                "element": element,
                                "value": pickled_value,
                            },
                        )
                except Exception:
                    pass

    op.drop_column("simulations", "metadata")
