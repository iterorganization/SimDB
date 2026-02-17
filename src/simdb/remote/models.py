from datetime import datetime as dt
from datetime import timezone
from typing import Annotated, Any, Generic, List, Optional, TypeVar, Union
from urllib.parse import urlencode
from uuid import UUID, uuid1

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    PlainSerializer,
    RootModel,
    model_validator,
)

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


class StatusPatchData(BaseModel):
    status: str


class DeletedSimulation(BaseModel):
    uuid: UUID
    files: List[str]


class SimulationDeleteResponse(BaseModel):
    deleted: DeletedSimulation


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


class FileDataList(RootModel):
    root: List[FileData] = []

    # Allows indexing: users[0]
    def __getitem__(self, item) -> FileData:
        return self.root[item]


class MetadataData(BaseModel):
    element: str
    value: Union[CustomUUID, Any]

    def as_dict(self):
        return {self.element: self.value}

    def as_querystring(self):
        return urlencode(self.as_dict())


class MetadataPatchData(BaseModel):
    key: str
    value: str


class MetadataDeleteData(BaseModel):
    key: str


class MetadataDataList(RootModel):
    root: List[MetadataData] = []

    def __getitem__(self, item) -> MetadataData:
        return self.root[item]

    def as_dict(self):
        return {m.element: m.value for m in self.root}

    @model_validator(mode="before")
    @classmethod
    def parse_dictionary(cls, data: Any):
        if isinstance(data, dict):
            return [{"element": k, "value": v} for (k, v) in data.items()]
        return data

    def as_querystring(self):
        return urlencode(self.as_dict())


class SimulationReference(BaseModel):
    uuid: CustomUUID
    alias: Optional[str] = None


class SimulationData(BaseModel):
    uuid: CustomUUID = Field(default_factory=lambda: uuid1())
    alias: Optional[str] = None
    datetime: dt = Field(default_factory=lambda: dt.now(timezone.utc))
    inputs: FileDataList = FileDataList()
    outputs: FileDataList = FileDataList()
    metadata: MetadataDataList = MetadataDataList()


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
    metadata: Optional[MetadataDataList] = None


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    count: int
    page: int
    limit: int
    results: List[T]


class PaginationData(BaseModel):
    limit: int
    page: int
    sort_by: str
    sort_asc: bool

    @model_validator(mode="before")
    @classmethod
    def parse_headers(cls, data: Any):
        if not isinstance(data, dict):
            return data
        new_data = {
            "limit": data.get("simdb-result-limit", 100),
            "page": data.get("simdb-page", 1),
            "sort_by": data.get("simdb-sort-by", ""),
            "sort_asc": data.get("simdb-sort-asc", False),
        }
        return new_data


class SimulationTraceData(SimulationData):
    status: Optional[str] = None
    passed_on: Optional[Any] = None
    failed_on: Optional[Any] = None
    deprecated_on: Optional[Any] = None
    accepted_on: Optional[Any] = None
    not_validated_on: Optional[Any] = None
    deleted_on: Optional[Any] = None
    replaces: Optional["SimulationTraceData"] = None
    replaces_reason: Optional[Any] = None
