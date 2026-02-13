from urllib.parse import urlencode
from datetime import datetime as dt
from datetime import timezone
from typing import Annotated, Any, Dict, Generic, List, Optional, TypeVar, Union
from uuid import UUID, uuid1

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer

HexUUID = Annotated[UUID, PlainSerializer(lambda x: x.hex, return_type=str)]


def _deserialize_custom_uuid(v: Any) -> UUID:
    """Deserialize CustomUUID format back to UUID."""
    if isinstance(v, UUID):
        return v
    if isinstance(v, dict) and "hex" in v:
        return UUID(hex=v["hex"])
    raise ValueError(f"Cannot deserialize {v} to UUID")


CustomUUID = Annotated[
    UUID,
    BeforeValidator(_deserialize_custom_uuid),
    PlainSerializer(lambda x: {"_type": "uuid.UUID", "hex": x.hex}),
]


class FileData(BaseModel):
    type: str
    uri: str
    uuid: CustomUUID = Field(default_factory=lambda: uuid1())
    checksum: str
    datetime: dt
    usage: Optional[str] = None
    purpose: Optional[str] = None
    sensitivity: Optional[str] = None
    access: Optional[str] = None
    embargo: Optional[str] = None


class MetadataData(BaseModel):
    element: str
    value: Union[CustomUUID, Any]

    def as_dict(self):
        return {self.element: self.value}

    def as_querystring(self):
        return urlencode(self.as_dict())


class SimulationReference(BaseModel):
    uuid: CustomUUID
    alias: Optional[str] = None


class SimulationData(BaseModel):
    uuid: CustomUUID = Field(default_factory=lambda: uuid1())
    alias: Optional[str] = None
    datetime: dt = Field(default_factory=lambda: dt.now(timezone.utc))
    inputs: List[FileData] = []
    outputs: List[FileData] = []
    metadata: List[MetadataData] = []


class SimulationDataResponse(SimulationData):
    parents: List[SimulationReference]
    children: List[SimulationReference]


class SimulationPostData(BaseModel):
    simulation: SimulationData
    add_watcher: bool
    uploaded_by: Optional[str] = None


class ValidationResult(BaseModel):
    passed: bool
    error: Optional[str] = None


class SimulationPostResponse(BaseModel):
    ingested: HexUUID
    error: Optional[str] = None
    validation: Optional[ValidationResult] = None


class SimulationListItem(BaseModel):
    uuid: CustomUUID
    alias: Optional[str] = None
    datetime: str
    metadata: Optional[List[MetadataData]] = None


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    count: int
    page: int
    limit: int
    results: List[T]
