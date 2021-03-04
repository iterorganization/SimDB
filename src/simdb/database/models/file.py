import uuid
from datetime import datetime
from typing import Dict

import uri as urilib
from dateutil import parser as date_parser
from sqlalchemy import Column, types as sql_types

from ...cli.manifest import DataObject
from . import Base
from .types import UUID, URI
from ...docstrings import inherit_docstrings


def _generate_checksum(type: DataObject.Type, uri: urilib.URI) -> str:
    if type == DataObject.Type.UDA:
        """
        URI: uda:///?signal=<SIGNAL>&source=<SOURCE>
        """
        from ...uda.checksum import checksum as uda_checksum
        checksum = uda_checksum(uri)
    elif type == DataObject.Type.IMAS:
        """
        URI: imas:///?shot=<SHOT>&run=<RUN>&machine=<MACHINE>&user=<USER>
        """
        from ...imas.checksum import checksum as imas_checksum
        checksum = imas_checksum(uri)
    elif type == DataObject.Type.FILE:
        """
        URI: file:///path/to/file
        """
        from ...checksum import sha1_checksum
        checksum = sha1_checksum(uri.path)
    else:
        raise NotImplementedError("Cannot generate checksum for type " + str(type))
    return checksum


@inherit_docstrings
class File(Base):
    """
    Class to represent files in the database ORM.
    """
    __tablename__ = "files"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False, unique=True)
    usage = Column(sql_types.String(250), nullable=True)
    uri: urilib.URI = Column(URI(1024), nullable=True)
    checksum = Column(sql_types.String(40), nullable=True)
    type: DataObject.Type = Column(sql_types.Enum(DataObject.Type), nullable=True)
    purpose = Column(sql_types.String(250), nullable=True)
    sensitivity = Column(sql_types.String(20), nullable=True)
    access = Column(sql_types.String(20), nullable=True)
    embargo = Column(sql_types.String(20), nullable=True)
    datetime = Column(sql_types.DateTime, nullable=False)

    def _integrity_check(self) -> None:
        self.checksum = _generate_checksum(self.type, self.uri)

    def __init__(self, type: DataObject.Type, uri: urilib.URI, perform_integrity_check: bool=True) -> None:
        self.uuid = uuid.uuid1()
        self.uri = uri
        self.type = type
        self.datetime = datetime.now()

        if perform_integrity_check:
            self._integrity_check()

    def __str__(self):
        result = ""
        for name in ("uuid", "usage", "uri", "checksum", "type", "purpose", "sensitivity", "access",
                     "embargo", "datetime"):
            result += "  %s:%s%s\n" % (name, ((14 - len(name)) * " "), getattr(self, name))
        return result

    def __repr__(self):
        result = "%s (%s)" % (self.uuid, self.file_name)
        return result

    @classmethod
    def from_data(cls, data: Dict) -> "File":
        file = File(DataObject.Type[data["type"]], urilib.URI(data["uri"]), perform_integrity_check=False)
        file.uuid = uuid.UUID(data["uuid"])
        file.usage = data["usage"]
        file.checksum = data["checksum"]
        file.purpose = data["purpose"]
        file.sensitivity = data["sensitivity"]
        file.access = data["access"]
        file.embargo = data["embargo"]
        file.datetime = date_parser.parse(data["datetime"])
        return file

    def data(self, recurse: bool=False) -> Dict[str, str]:
        data = dict(
            uuid=self.uuid.hex,
            usage=self.usage,
            uri=str(self.uri),
            checksum=self.checksum,
            type=self.type.name,
            purpose=self.purpose,
            sensitivity=self.sensitivity,
            access=self.access,
            embargo=self.embargo,
            datetime=self.datetime.isoformat(),
        )
        return data
