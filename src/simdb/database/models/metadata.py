from typing import Any, Dict

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import types as sql_types

from simdb.docstrings import inherit_docstrings
from simdb.remote.models import MetadataData

from .base import Base


@inherit_docstrings
class MetaData(Base):
    """
    Class to represent metadata in the database ORM.
    """

    __tablename__ = "metadata"
    id = Column(sql_types.Integer, primary_key=True)
    sim_id = Column(sql_types.Integer, ForeignKey("simulations.id"), index=True)
    element = Column(sql_types.String(250), nullable=False)
    value = Column(sql_types.PickleType(0), nullable=True)

    def __init__(self, key: str, value: Any) -> None:
        self.element = key
        self.value = value

    def __str__(self):
        return f"{self.element}: {self.value}"

    @classmethod
    def from_data(cls, data: Dict) -> "MetaData":
        meta = MetaData(data["element"], data["value"])
        return meta

    @classmethod
    def from_data_model(cls, data: MetadataData) -> "MetaData":
        meta = MetaData(data.element, data.value)
        return meta

    def data(self, recurse: bool = False) -> Dict[str, str]:
        data = {
            "element": self.element,
            "value": self.value,
        }
        return data

    def to_model(self) -> MetadataData:
        return MetadataData(element=self.element, value=self.value)


Index("metadata_index", MetaData.sim_id, MetaData.element, unique=True)
