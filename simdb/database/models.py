from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, CHAR, String, Integer, DateTime
from sqlalchemy.dialects import postgresql
import uuid
import os
from typing import Union
from datetime import datetime
from dateutil import parser as date_parser

from ..cli.manifest import Manifest, Source

Base = declarative_base()


class UUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as stringified hex values.
    """
    impl = CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value).hex
            else:
                return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


simulation_files = Table("simulation_files", Base.metadata,
                         Column("simulation_id", Integer, ForeignKey("simulations.id")),
                         Column("file_id", Integer, ForeignKey("files.id")))


class Simulation(Base):
    __tablename__ = "simulations"
    id = Column(Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    alias = Column(String(250), nullable=True)
    datetime = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False)
    files = relationship("File", secondary=simulation_files, backref="simulations")

    def __init__(self, manifest: Union[Manifest, None]):
        if manifest is None:
            return
        self.uuid = uuid.uuid1()
        self.datetime = datetime.now()
        self.status = "UNKNOWN"
        for source in manifest.inputs:
            if source.type == Source.Type.PATH:
                self.files.append(File(source))

    def __str__(self):
        result = ""
        for name in ("uuid", "alias", "datetime", "status"):
            result += "  %s:%s%s\n" % (name, ((10 - len(name)) * " "), getattr(self, name))
        result += "files:\n"
        for file in self.files:
            result += "%s\n" % file
        return result

    @classmethod
    def from_data(cls, data: dict) -> "Simulation":
        simulation = Simulation(None)
        simulation.uuid = uuid.UUID(data["uuid"])
        simulation.datetime = date_parser.parse(data["datetime"])
        simulation.status = data["status"]
        simulation.files = [File.from_data(d) for d in data["files"]]
        return simulation

    def data(self) -> dict:
        data = dict(
            uuid=self.uuid.hex,
            datetime=self.datetime.isoformat(),
            status=self.status,
            files=[f.data() for f in self.files],
        )
        return data


class MetaData(Base):
    __tablename__ = "metadata"
    id = Column(Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    element = Column(String(250), nullable=False)
    value = Column(String(250), nullable=True)


class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    metadata_id = Column(Integer, ForeignKey(MetaData.id))
    usage = Column(String(250), nullable=True)
    file_name = Column(String(250), nullable=False)
    directory = Column(String(250), nullable=True)
    checksum = Column(String(40), nullable=True)
    type = Column(String(20), nullable=True)
    purpose = Column(String(250), nullable=True)
    sensitivity = Column(String(20), nullable=True)
    access = Column(String(20), nullable=True)
    embargo = Column(String(20), nullable=True)
    datetime = Column(DateTime, nullable=False)

    def __init__(self, source: Union[Source, None]):
        if source is None:
            return
        self.uuid = uuid.uuid1()
        self.file_name = os.path.basename(source.name)
        self.directory = os.path.dirname(source.name)
        self.checksum = source.checksum
        self.type = source.type.name
        self.datetime = datetime.now()

    def __str__(self):
        result = ""
        for name in ("uuid", "usage", "file_name", "directory", "checksum", "type", "purpose", "sensitivity", "access",
                     "embargo", "datetime"):
            result += "  %s:%s%s\n" % (name, ((14 - len(name)) * " "), getattr(self, name))
        return result

    @classmethod
    def from_data(cls, data: dict):
        file = File(None)
        file.uuid = uuid.UUID(data["uuid"])
        file.usage = data["usage"]
        file.file_name = data["file_name"]
        file.directory = data["directory"]
        file.checksum = data["checksum"]
        file.type = data["type"]
        file.purpose = data["purpose"]
        file.sensitivity = data["sensitivity"]
        file.access = data["access"]
        file.embargo = data["embargo"]
        file.datetime = date_parser.parse(data["datetime"])
        return file

    def data(self) -> dict:
        data = dict(
            uuid=self.uuid.hex,
            usage=self.usage,
            file_name=self.file_name,
            directory=self.directory,
            checksum=self.checksum,
            type=self.type,
            purpose=self.purpose,
            sensitivity=self.sensitivity,
            access=self.access,
            embargo=self.embargo,
            datetime=self.datetime.isoformat(),
        )
        return data
