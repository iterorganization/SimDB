import uuid
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

import uri as urilib
from dateutil import parser as date_parser
from sqlalchemy import Column, types as sql_types

from ...cli.manifest import DataObject
from .base import Base
from .types import UUID, URI
from ...docstrings import inherit_docstrings
from ...config.config import Config


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
    checksum = Column(sql_types.String(64), nullable=True)
    type: DataObject.Type = Column(sql_types.Enum(DataObject.Type), nullable=True)
    purpose = Column(sql_types.String(250), nullable=True)
    sensitivity = Column(sql_types.String(20), nullable=True)
    access = Column(sql_types.String(20), nullable=True)
    embargo = Column(sql_types.String(20), nullable=True)
    datetime = Column(sql_types.DateTime, nullable=False)

    def __init__(self, type: DataObject.Type, uri: urilib.URI, perform_integrity_check: bool=True,
                 config: Optional[Config]=None) -> None:
        self.uuid = uuid.uuid1()
        self.uri = uri
        self.type = type

        if perform_integrity_check:
            self.datetime = self.get_creation_date()
            self.checksum = self.generate_checksum(config)

    def __str__(self):
        result = ""
        for name in ("uuid", "usage", "uri", "checksum", "type", "purpose", "sensitivity", "access",
                     "embargo", "datetime"):
            result += "  %s:%s%s\n" % (name, ((14 - len(name)) * " "), getattr(self, name))
        return result

    def __repr__(self):
        result = f"{self.uuid} ({self.uri})"
        return result

    def generate_checksum(self, config):
        if config and config.get_option('development.disable_checksum', default=False):
            return ''
        if self.type == DataObject.Type.UDA:
            from ...uda.checksum import checksum as uda_checksum
            checksum = uda_checksum(self.uri)
        elif self.type == DataObject.Type.IMAS:
            from ...imas.checksum import checksum as imas_checksum
            checksum = imas_checksum(self.uri)
        elif self.type == DataObject.Type.FILE:
            from ...checksum import sha1_checksum
            checksum = sha1_checksum(self.uri)
        else:
            raise NotImplementedError(f"Cannot generate checksum for type {self.type}.")
        return checksum

    def get_creation_date(self) -> datetime:
        if self.type == DataObject.Type.UDA:
            return datetime.now()
        elif self.type == DataObject.Type.IMAS:
            from ...imas.utils import imas_timestamp
            return imas_timestamp(self.uri)
        elif self.type == DataObject.Type.FILE:
            return datetime.fromtimestamp(Path(self.uri.path).stat().st_ctime)
        else:
            raise NotImplementedError(f"Cannot generate checksum for type {self.type}.")

    def validate_checksum(self) -> bool:
        checksum = self.get_creation_date()
        return checksum == self.checksum

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
