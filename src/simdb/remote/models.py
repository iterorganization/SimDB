"""Pydantic models for the SimDB remote API."""

import base64
from datetime import datetime as dt
from datetime import timezone
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    TypeVar,
    Union,
)
from urllib.parse import urlencode
from uuid import UUID, uuid1

import numpy as np
from pydantic import (
    BaseModel as _BaseModel,
)
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    InstanceOf,
    PlainSerializer,
    model_validator,
)
from pydantic import (
    RootModel as _RootModel,
)

from simdb.cli.manifest import DataObject

HexUUID = Annotated[UUID, PlainSerializer(lambda x: x.hex, return_type=str)]
"""UUID serialized as a hex string."""


class BaseModel(_BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)


class RootModel(_RootModel):
    model_config = ConfigDict(use_attribute_docstrings=True)


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
"""UUID with custom serialization format."""

StatusLiteral = Literal[
    "not validated", "accepted", "failed", "passed", "deprecated", "deleted"
]
"""String representation of a simulation status"""


class StatusPatchData(BaseModel):
    """Post data for updating simulation status."""

    status: StatusLiteral
    """New simulation status."""


class DeletedSimulation(BaseModel):
    """Reference to a deleted simulation."""

    simulation: UUID
    """UUID of the deleted simulation."""
    files: List[str]
    """List of deleted file paths."""


class SimulationDeleteResponse(BaseModel):
    """Response from DELETE v1.2/simulations/{uuid}."""

    deleted: DeletedSimulation
    """Reference to the deleted simulation."""


class FileData(BaseModel):
    """Model representing a file in the system."""

    type: Literal["UNKNOWN", "UUID", "FILE", "IMAS"]
    """File type."""
    uri: str
    """URI to the file location."""
    uuid: CustomUUID = Field(default_factory=lambda: uuid1())
    """Unique identifier for the file."""
    checksum: str
    """Checksum of the file."""
    datetime: dt
    """Timestamp of the file."""
    usage: Optional[str] = None
    """File usage description."""
    purpose: Optional[str] = None
    """Purpose of the file."""
    sensitivity: Optional[str] = None
    """Sensitivity level of the file."""
    access: Optional[str] = None
    """Access permissions."""
    embargo: Optional[str] = None
    """Embargo information."""


class FileDataList(RootModel):
    """List of FileData items."""

    root: List[FileData] = []

    def __getitem__(self, item) -> FileData:
        """Allow indexing on the list."""
        return self.root[item]


def _deserialize_numpy(v: Any) -> Any:
    if isinstance(v, np.ndarray):
        return v
    if isinstance(v, dict) and v.get("_type") == "numpy.ndarray":
        np_bytes = base64.b64decode(v["bytes"].encode())
        return np.frombuffer(np_bytes, dtype=v["dtype"]).reshape(v["shape"])
    raise ValueError(f"Cannot deserialize {v} to np.ndarray")


def _serialize_numpy(o: np.ndarray) -> dict:
    """Serialize numpy arrays to dict format for the web dashboard."""
    encoded_bytes = base64.b64encode(o.data).decode()
    return {
        "_type": "numpy.ndarray",
        "dtype": o.dtype.name,
        "shape": o.shape,
        "bytes": encoded_bytes,
    }


NumpyArray = Annotated[
    InstanceOf[np.ndarray],
    BeforeValidator(_deserialize_numpy),
    PlainSerializer(_serialize_numpy, return_type=dict),
]


MetadataValue = Union[
    CustomUUID,
    str,
    int,
    float,
    bool,
    list,
    dict,
    NumpyArray,
    None,
]
"""Supported types for simulation metadata values. Numpy arrays and scalars are
automatically converted to their plain Python equivalents before validation."""


class MetadataData(BaseModel):
    """Key-value pair for simulation metadata."""

    element: str
    """Metadata key/name."""
    value: MetadataValue
    """Metadata value."""

    def as_dict(self) -> dict:
        """Convert to dictionary."""
        return {self.element: self.value}

    def as_querystring(self) -> str:
        """Convert to URL query string."""
        return urlencode(self.as_dict())


class MetadataPatchData(BaseModel):
    """Data for patching a metadata entry."""

    key: str
    """Metadata key to update."""
    value: str
    """New value for the metadata key."""


class MetadataDeleteData(BaseModel):
    """Data for deleting a metadata entry."""

    key: str
    """Metadata key to delete."""


class MetadataDataList(RootModel):
    """List of MetadataData items."""

    root: List[MetadataData] = []

    def __getitem__(self, item) -> MetadataData:
        """Allow indexing on the list."""
        return self.root[item]

    def as_dict(self) -> dict:
        """Convert all metadata to dictionary."""
        return {m.element: m.value for m in self.root}

    @model_validator(mode="before")
    @classmethod
    def parse_dictionary(cls, data: Any):
        """Parse dictionary to list of MetadataData."""
        if isinstance(data, dict):
            return [{"element": k, "value": v} for (k, v) in data.items()]
        return data

    def as_querystring(self) -> str:
        """Convert to URL query string."""
        return urlencode(self.as_dict())


class MetadataDeleteResponse(BaseModel):
    pass


class MetadataKeyInfo(BaseModel):
    """Information about a metadata key."""

    name: str
    """Metadata key name."""
    type: str
    """Python type name of the metadata value."""


class MetadataKeyInfoList(RootModel):
    """List of metadata key info items."""

    root: List[MetadataKeyInfo] = []


class MetadataValueList(RootModel):
    """List of metadata values for a given key."""

    root: List[MetadataValue] = []


class SimulationReference(BaseModel):
    """Reference to a simulation."""

    uuid: CustomUUID
    """UUID of the simulation."""
    alias: Optional[str] = None
    """Alias of the simulation."""


class SimulationData(BaseModel):
    """Core simulation data."""

    uuid: CustomUUID = Field(default_factory=lambda: uuid1())
    """Unique identifier of the simulation."""
    alias: Optional[str] = None
    """Human-readable alias."""
    datetime: dt = Field(default_factory=lambda: dt.now(timezone.utc))
    """Creation timestamp."""
    inputs: FileDataList = FileDataList()
    """List of input files."""
    outputs: FileDataList = FileDataList()
    """List of output files."""
    metadata: MetadataDataList = MetadataDataList()
    """Simulation metadata."""


class SimulationDataResponse(SimulationData):
    """Simulation data with parent/child references."""

    parents: List[SimulationReference]
    """Parent simulations."""
    children: List[SimulationReference]
    """Child simulations."""


class SimulationPatchResponse(BaseModel):
    pass


class SimulationPostData(BaseModel):
    """Data for creating a new simulation."""

    simulation: SimulationData
    """The simulation data to create."""
    add_watcher: bool
    """Whether to add a watcher for this simulation."""
    uploaded_by: Optional[str] = None
    """User who uploaded the simulation."""


class ValidationResult(BaseModel):
    """Result of simulation validation."""

    passed: bool
    """Whether validation passed."""
    error: Optional[str] = None
    """Error message if validation failed."""


class SimulationPostResponse(BaseModel):
    """Response from creating a simulation."""

    ingested: HexUUID
    """UUID of the ingested simulation."""
    error: Optional[str] = None
    """Error message if ingestion failed."""
    validation: Optional[ValidationResult] = None
    """Validation result."""


class SimulationListItem(BaseModel):
    """Summary of a simulation for list views."""

    uuid: CustomUUID
    """UUID of the simulation."""
    alias: Optional[str] = None
    """Alias of the simulation."""
    datetime: str
    """Creation timestamp."""
    metadata: Optional[MetadataDataList] = None
    """Simulation metadata."""


T = TypeVar("T")
"""Type variable for generic paginated responses."""


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    count: int
    """Total number of items."""
    page: int
    """Current page number."""
    limit: int
    """Number of items per page."""
    results: List[T]
    """List of results for this page."""


class PaginationData(BaseModel):
    """Pagination parameters from request headers.

    Fields are populated from HTTP headers. The field aliases match the
    lowercased header names as provided by Werkzeug / ``_validate_param``.
    Use ``model_validate`` with ``by_alias=False`` (the default) or pass a
    dict with the alias keys; Pydantic will resolve them via the
    ``model_config`` ``populate_by_name=True`` setting.
    """

    model_config = ConfigDict(populate_by_name=True, use_attribute_docstrings=True)

    limit: int = Field(100, alias="simdb-result-limit")
    """Number of items per page."""
    page: int = Field(1, alias="simdb-page")
    """Current page number."""
    sort_by: str = Field("", alias="simdb-sort-by")
    """Field to sort by."""
    sort_asc: bool = Field(False, alias="simdb-sort-asc")
    """Whether to sort ascending."""


class SimulationTraceData(SimulationData):
    """Simulation data with status history."""

    status: Optional[StatusLiteral] = None
    """Current status of the simulation."""
    passed_on: Optional[Any] = None
    """Timestamp when status changed to passed."""
    failed_on: Optional[Any] = None
    """Timestamp when status changed to failed."""
    deprecated_on: Optional[Any] = None
    """Timestamp when status changed to deprecated."""
    accepted_on: Optional[Any] = None
    """Timestamp when status changed to accepted."""
    not_validated_on: Optional[Any] = None
    """Timestamp when status changed to not validated."""
    deleted_on: Optional[Any] = None
    """Timestamp when status changed to deleted."""
    replaces: Optional["SimulationTraceData"] = None
    """Simulation this one replaces."""
    replaces_reason: Optional[Any] = None
    """Reason for replacement."""


class ChunkInfo(BaseModel):
    """Information about a single chunk in a chunked file upload."""

    chunk_size: int
    """Length of the chunk."""
    chunk: int
    """Index of the chunk."""
    num_chunks: Optional[int] = 1
    """Total amount of chunks in the file."""


class ChunkInfoDict(RootModel):
    """Dictionary mapping file UUID hex to chunk info."""

    root: Dict[str, ChunkInfo]


class FileUploadData(BaseModel):
    """Data payload for file chunk upload (sent as JSON in 'data' field)."""

    simulation: SimulationData
    """The simulation the file belongs to."""
    file_type: str
    """Type of the file."""
    chunk_info: Optional[Dict[str, ChunkInfo]] = None
    """Info about the chunk."""


class FilesGetResponse(RootModel):
    """Response from the get files endpoint."""

    root: List[FileData]
    """List of files."""


class FileInfo(BaseModel):
    """Information about a single file on disk."""

    path: Path
    """Path to the file."""
    checksum: str
    """Checksum of the file."""


class FileGetDataResponse(FileData):
    """Response from the get file data endpoint, extending FileData with disk info."""

    files: List[FileInfo]
    """List of file info entries for the files on disk."""


class FileUploadResponse(BaseModel):
    """Response from file upload/chunk upload endpoint."""

    pass


class FileRegistrationItem(BaseModel):
    """A single file entry in the file registration payload."""

    chunks: int
    """The amount of chunks to be processed."""
    file_type: str
    """The file type."""
    file_uuid: HexUUID
    """The UUID of the file."""
    ids_list: Optional[List[Any]] = None
    """List of IDS names associated with the file."""


class FileRegistrationData(BaseModel):
    """Payload for final file registration after chunk uploads."""

    simulation: SimulationData
    """The simulation the files belong to."""
    obj_type: DataObject.Type
    """The type of the data object being registered."""
    files: List[FileRegistrationItem]
    """List of file registration items."""


class FileRegistrationResponse(BaseModel):
    """Response from file registration endpoint."""

    pass


class WatcherReference(BaseModel):
    """An watcher entry reference."""

    simulation: HexUUID
    """Simulation UUID the watcher has been added to."""
    watcher: str
    """Username of the added watcher."""


class WatcherPostResponse(BaseModel):
    """Response from the add watcher endpoint."""

    added: WatcherReference
    """The added watcher data."""


class WatcherPostRequest(BaseModel):
    """Payload for adding a watcher to a simulation."""

    user: Optional[str]
    """Username of the watcher, defaults to the signed in user."""
    email: Optional[str]
    """Email of the watcher, defaults to the signed in user."""
    notification: Literal["VALIDATION", "REVISION", "OBSOLESCENCE", "ALL"]
    """Notificaiton type of the watcher."""


class WatcherData(BaseModel):
    """Payload describing a watcher."""

    username: str
    """Username of the watcher."""
    email: str
    """Email address of the watcher."""
    notification: Literal["V", "R", "O", "A"]
    """Notification type of the watcher.
        Types are: V(alidation), R(evision), O(bsolescence) and A(ll)
    """


class WatcherGetResponse(RootModel):
    """Response from the get watchers endpoint."""

    root: List[WatcherData]


class WatcherDeleteRequest(BaseModel):
    """Payload for deleting a watcher from a simulation."""

    user: str
    """Username to delete from the watchers."""


class WatcherDeleteResponse(BaseModel):
    """Response from the delete watchers endpoint."""

    removed: WatcherReference
    """Reference to the deleted wacher."""


class StagingDirectoryResponse(BaseModel):
    """Response from the get staging dir endpoint."""

    staging_dir: Path
    """Path to the staging dir."""


class ErrorResponse(BaseModel):
    """Response model for server errors."""

    error: str
    """Error description."""
