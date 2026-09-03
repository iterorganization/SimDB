"""normalise_ids_metadata_to_list

Convert the ``ids`` and ``input_ids`` simulation metadata from their display-string
form, ``"[core_profiles, equilibrium]"``, to a real list of IDS names.

Revision ID: a3f1c7d94e02
Revises: 6fb9b8fbac38
Create Date: 2026-09-01 00:00:00.000000

"""

import json
from typing import Any, Sequence, Union

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f1c7d94e02"
down_revision: Union[str, Sequence[str], None] = "6fb9b8fbac38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IDS_KEYS = ("ids", "input_ids")

_SELECT = text("SELECT id, metadata FROM simulations WHERE metadata IS NOT NULL")
_UPDATE = text("UPDATE simulations SET metadata = :metadata WHERE id = :sim_id")


def _as_dict(value: Any) -> Any:
    """Return the metadata column value as a dict.

    SQLite hands back the raw JSON text while PostgreSQL decodes JSONB for us.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def _split_ids(value: str) -> list:
    text_value = value.strip()
    if text_value.startswith("[") and text_value.endswith("]"):
        text_value = text_value[1:-1]
    return [name.strip() for name in text_value.split(",") if name.strip()]


def _convert(convert_value) -> None:
    conn = op.get_bind()
    rows = conn.execute(_SELECT).fetchall()

    for sim_id, metadata in rows:
        meta_dict = _as_dict(metadata)
        if not meta_dict:
            continue

        changed = False
        for key in IDS_KEYS:
            if key not in meta_dict:
                continue
            new_value = convert_value(meta_dict[key])
            if new_value is not None and new_value != meta_dict[key]:
                meta_dict[key] = new_value
                changed = True

        if changed:
            conn.execute(_UPDATE, {"metadata": json.dumps(meta_dict), "sim_id": sim_id})


def upgrade() -> None:
    """Turn stringified IDS lists into real lists."""

    def to_list(value: Any) -> Any:
        return _split_ids(value) if isinstance(value, str) else None

    _convert(to_list)


def downgrade() -> None:
    """Restore the display-string form of the IDS lists."""

    def to_string(value: Any) -> Any:
        if isinstance(value, list):
            return "[{}]".format(", ".join(str(el) for el in value))
        return None

    _convert(to_string)
