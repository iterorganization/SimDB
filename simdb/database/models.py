from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, CHAR, String, Integer, DateTime, Enum, Text
from sqlalchemy.dialects import postgresql
import uuid
import os
from typing import Union, List
from datetime import datetime
from dateutil import parser as date_parser

from ..cli.manifest import Manifest, DataObject
from ..utils import inherit_docstrings, format_docstring


class UUID(TypeDecorator):
    """
    Platform-independent GUID type.

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


class BaseModel:
    """
    Base model for ORM classes.
    """
    def __str__(self):
        """
        Return a string representation of the {cls.__name__} formatted to print.

        :return: The {cls.__name__} as a string for printing.
        """
        raise NotImplementedError

    @classmethod
    def from_data(cls, data: dict) -> "BaseModel":
        """
        Create a Model from serialised data.

        :param data: Serialised model data.
        :return: The created model.
        """
        raise NotImplementedError

    def data(self, recurse: bool=False) -> dict:
        """
        Serialise the {cls.__name__}.

        :param recurse: If True also serialise any contained models, otherwise only serialise simple fields.
        :return: The serialised data.
        """
        raise NotImplementedError


Base = declarative_base(cls=BaseModel)


simulation_files = Table("simulation_files", Base.metadata,
                         Column("simulation_id", Integer, ForeignKey("simulations.id")),
                         Column("file_id", Integer, ForeignKey("files.id")))


@inherit_docstrings
class Simulation(Base):
    """
    Class to represent simulations in the database ORM.
    """
    __tablename__ = "simulations"
    id = Column(Integer, primary_key=True)
    uuid = Column(UUID, nullable=False, unique=True)
    # metadata_id = Column(Integer, ForeignKey(MetaData.id))
    alias = Column(String(250), nullable=True, unique=True)
    datetime = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False)
    files: List["File"] = relationship("File", secondary=simulation_files, backref="simulations")
    meta = relationship("MetaData")

    def __init__(self, manifest: Union[Manifest, None]):
        """
        Initialise a new Simulation object using the provided Manifest.

        :param manifest: The Manifest to load the data from, or None to create an empty Simulation.
        """
        if manifest is None:
            return
        self.uuid = uuid.uuid1()
        self.datetime = datetime.now()
        self.status = "UNKNOWN"

        for source in manifest.inputs:
            if source.type == DataObject.Type.PATH:
                self.files.append(File(source))

        for key, value in manifest.metadata.items():
            self.meta.append(MetaData(key, str(value)))

    def __str__(self):
        result = ""
        for name in ("uuid", "alias", "datetime", "status"):
            result += "%s:%s%s\n" % (name, ((10 - len(name)) * " "), getattr(self, name))
        result += "metdata:\n"
        for meta in self.meta:
            result += "  %s: %s\n" % (meta.element, meta.value)
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
        if "files" in data:
            simulation.files = [File.from_data(d) for d in data["files"]]
        if "metadata" in data:
            for d in data["metadata"]:
                simulation.meta.append(MetaData.from_data(d))
        return simulation

    def data(self, recurse: bool=False) -> dict:
        data = dict(
            uuid=self.uuid.hex,
            datetime=self.datetime.isoformat(),
            status=self.status,
        )
        if recurse:
            data["files"] = [f.data(recurse=True) for f in self.files]
            data["metadata"] = [m.data(recurse=True) for m in self.meta]
        return data


@inherit_docstrings
class File(Base):
    """
    Class to represent files in the database ORM.
    """
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    uuid = Column(UUID, nullable=False, unique=True)
    usage = Column(String(250), nullable=True)
    file_name = Column(String(250), nullable=False)
    directory = Column(String(250), nullable=True)
    checksum = Column(String(40), nullable=True)
    type: DataObject.Type = Column(Enum(DataObject.Type), nullable=True)
    purpose = Column(String(250), nullable=True)
    sensitivity = Column(String(20), nullable=True)
    access = Column(String(20), nullable=True)
    embargo = Column(String(20), nullable=True)
    datetime = Column(DateTime, nullable=False)

    def __init__(self, data_object: Union[DataObject, None]):
        """
        Initialise the File object using the provided DataObject.

        :param data_object: The DataObject to load the data from, or None to create an empty File.
        """
        if data_object is None:
            return
        self.uuid = uuid.uuid1()
        self.file_name = os.path.basename(data_object.name)
        self.directory = os.path.dirname(data_object.name)
        self.checksum = data_object.checksum
        self.type = data_object.type
        self.datetime = datetime.now()

    def __str__(self):
        result = ""
        for name in ("uuid", "usage", "file_name", "directory", "checksum", "type", "purpose", "sensitivity", "access",
                     "embargo", "datetime"):
            result += "  %s:%s%s\n" % (name, ((14 - len(name)) * " "), getattr(self, name))
        return result

    def __repr__(self):
        result = "%s (%s)" % (self.uuid, self.file_name)
        return result

    @classmethod
    def from_data(cls, data: dict) -> "File":
        file = File(None)
        file.uuid = uuid.UUID(data["uuid"])
        file.usage = data["usage"]
        file.file_name = data["file_name"]
        file.directory = data["directory"]
        file.checksum = data["checksum"]
        file.type = DataObject.Type[data["type"]]
        file.purpose = data["purpose"]
        file.sensitivity = data["sensitivity"]
        file.access = data["access"]
        file.embargo = data["embargo"]
        file.datetime = date_parser.parse(data["datetime"])
        return file

    def data(self, recurse: bool=False) -> dict:
        data = dict(
            uuid=self.uuid.hex,
            usage=self.usage,
            file_name=self.file_name,
            directory=self.directory,
            checksum=self.checksum,
            type=self.type.name,
            purpose=self.purpose,
            sensitivity=self.sensitivity,
            access=self.access,
            embargo=self.embargo,
            datetime=self.datetime.isoformat(),
        )
        return data


@inherit_docstrings
class MetaData(Base):
    """
    Class to represent metadata in the database ORM.
    """
    __tablename__ = "metadata"
    id = Column(Integer, primary_key=True)
    sim_id = Column(Integer, ForeignKey(Simulation.id))
    uuid = Column(UUID, nullable=False)
    element = Column(String(250), nullable=False)
    value = Column(Text, nullable=True)

    def __init__(self, key: str, value: str):
        self.uuid = uuid.uuid1()
        self.element = key
        self.value = value

    @classmethod
    def from_data(cls, data: dict) -> "MetaData":
        meta = MetaData(data["element"], data["value"])
        meta.uuid = data["uuid"]
        return meta

    def data(self, recurse: bool=False) -> dict:
        data = dict(
            uuid=self.uuid.hex,
            element=self.element,
            value=self.value,
        )
        return data
