import uuid
from typing import Dict

from sqlalchemy import Column, types as sql_types, ForeignKey, UniqueConstraint

from ._base import Base
from .simulation import Simulation
from .types import UUID
from ...docstrings import inherit_docstrings


@inherit_docstrings
class Summary(Base):
    """
    Class to represent metadata in the database ORM.
    """
    __tablename__ = "summary"
    id = Column(sql_types.Integer, primary_key=True)
    sim_id = Column(sql_types.Integer, ForeignKey(Simulation.id))
    uuid = Column(UUID, nullable=False)
    key = Column(sql_types.String(250), nullable=False)
    value = Column(sql_types.Text, nullable=True)

    __table_args__ = (
        UniqueConstraint('sim_id', 'key', name='_simulation_summary'),
    )

    def __init__(self, key: str, value: str) -> None:
        self.uuid = uuid.uuid1()
        self.key = key
        self.value = value

    @classmethod
    def from_data(cls, data: Dict) -> "Summary":
        summary = Summary(data["key"], data["value"])
        summary.uuid = data["uuid"]
        return summary

    def data(self, recurse: bool=False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            key=self.key,
            value=self.value,
        )
        return data
