import uuid
from typing import Dict, Any

from sqlalchemy import Column, types as sql_types, ForeignKey, Index

# from .types import UUID
from .base import Base
from .simulation import Simulation
from ...docstrings import inherit_docstrings


@inherit_docstrings
class MetaData(Base):
    """
    Class to represent metadata in the database ORM.
    """
    __tablename__ = "metadata"
    id = Column(sql_types.Integer, primary_key=True)
    sim_id = Column(sql_types.Integer, ForeignKey(Simulation.id), index=True)
    element = Column(sql_types.String(250), nullable=False)
    value = Column(sql_types.PickleType(4), nullable=True)

    def __init__(self, key: str, value: Any) -> None:
        self.uuid = uuid.uuid1()
        self.element = key
        self.value = value

    def __str__(self):
        return "{}: {}".format(self.element, self.value)

    @classmethod
    def from_data(cls, data: Dict) -> "MetaData":
        meta = MetaData(data["element"], data["value"])
        # meta.uuid = uuid.UUID(data["uuid"])
        return meta

    def data(self, recurse: bool=False) -> Dict[str, str]:
        data = dict(
            # uuid=self.uuid.hex,
            element=self.element,
            value=self.value,
        )
        return data


Index('metadata_index', MetaData.sim_id, MetaData.element, unique=True)
