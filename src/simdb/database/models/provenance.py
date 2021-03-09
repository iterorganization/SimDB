import uuid
from typing import Dict

from sqlalchemy import Column, types as sql_types, ForeignKey
from sqlalchemy.orm import relationship

from ._base import _flatten_dict
from .types import UUID
from ._base import Base
from .simulation import Simulation
from ...docstrings import inherit_docstrings


@inherit_docstrings
class Provenance(Base):
    """
    Class to represent provenance in the database ORM.
    """
    __tablename__ = "provenance"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    sim_id = Column(sql_types.Integer, ForeignKey(Simulation.id))
    meta = relationship("ProvenanceMetaData")
    signals = relationship("ProvenanceSignal")

    def __init__(self, metadata: Dict) -> None:
        self.uuid = uuid.uuid1()
        self.add_metadata(metadata)
        self.add_signals()

    def add_metadata(self, metadata: Dict):
        flattened_dict: Dict[str, str] = {}
        _flatten_dict(flattened_dict, metadata)

        for key, value in flattened_dict.items():
            self.meta.append(ProvenanceMetaData(key, value))

    def add_signals(self):
        pass

    @classmethod
    def from_data(cls, data: Dict) -> "Provenance":
        prov = Provenance(data["meta"])
        prov.uuid = data["uuid"]
        return prov

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            element=self.element,
            value=self.value,
        )
        if recurse:
            data["meta"] = [m.data(recurse=True) for m in self.meta]
        return data

    def __str__(self):
        s = "MetaData:\n"
        for meta in self.meta:
            s += ("  " + str(meta))
        s += "Signals:\n"
        for signal in self.signals:
            s += ("  " + str(signal))
        return s


@inherit_docstrings
class ProvenanceMetaData(Base):
    """
    Class to represent provenance metadata in the database ORM.
    """
    __tablename__ = "provenance_metadata"
    id = Column(sql_types.Integer, primary_key=True)
    prov_id = Column(sql_types.Integer, ForeignKey(Provenance.id))
    uuid = Column(UUID, nullable=False)
    element = Column(sql_types.String(250), nullable=False)
    value = Column(sql_types.Text, nullable=True)

    def __init__(self, key: str, value: str) -> None:
        self.uuid = uuid.uuid1()
        self.element = key
        self.value = value

    @classmethod
    def from_data(cls, data: Dict) -> "ProvenanceMetaData":
        meta = ProvenanceMetaData(data["element"], data["value"])
        meta.uuid = data["uuid"]
        return meta

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            element=self.element,
            value=self.value,
        )
        return data

    def __str__(self):
        s = "{}: {}\n".format(self.element, self.value)
        return s


@inherit_docstrings
class ProvenanceSignal(Base):
    """
    Class to represent provenance signal request in the database ORM.
    """
    __tablename__ = "provenance_signal"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    prov_id = Column(sql_types.Integer, ForeignKey(Provenance.id))
    requested_signal = Column(sql_types.Text, nullable=False)
    requested_source = Column(sql_types.Text, nullable=False)
    mapped_signal = Column(sql_types.Text, nullable=False)
    mapped_source = Column(sql_types.Text, nullable=False)
    mapped_source_uuid = Column(UUID, nullable=False)

    def __init__(self, requested_signal: str, requested_source: str, mapped_signal: str, mapped_source: str,
                 mapped_source_uuid: str) -> None:
        self.uuid = uuid.uuid1()
        self.requested_signal = requested_signal
        self.requested_source = requested_source
        self.mapped_signal = mapped_signal
        self.mapped_source = mapped_source
        self.mapped_source_uuid = uuid.UUID(mapped_source_uuid)

    @classmethod
    def from_data(cls, data: Dict) -> "ProvenanceMetaData":
        prov_signal = ProvenanceSignal(data["requested_signal"], data["requested_source"], data["mapped_signal"],
                                       data["mapped_source"], data["mapped_source_uuid"])
        prov_signal.uuid = data["uuid"]
        return prov_signal

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            requested_signal=self.requested_signal,
            requested_source=self.requested_source,
            mapped_signal=self.mapped_signal,
            mapped_source=self.mapped_source,
            mapped_source_uuid=self.mapped_source_uuid.hex,
        )
        return data
