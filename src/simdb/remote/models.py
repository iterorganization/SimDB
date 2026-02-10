from datetime import datetime as dt
from datetime import timezone
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FileData(BaseModel):
    type: str
    uri: str
    uuid: UUID
    checksum: str
    datetime: dt
    usage: Optional[str]
    purpose: Optional[str]
    sensitivity: Optional[str]
    access: Optional[str]
    embargo: Optional[str]


class MetadataData(BaseModel):
    element: str
    value: Any


class SimulationData(BaseModel):
    uuid: UUID
    alias: Optional[str]
    datetime: dt = Field(default_factory=lambda: dt.now(timezone.utc))
    inputs: List[FileData]
    outputs: List[FileData]
    metadata: List[MetadataData]


class SimulationPostData(BaseModel):
    simulation: SimulationData
    add_watcher: bool
    uploaded_by: Optional[str]
