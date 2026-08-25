import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO, Any, Protocol

from simdb.cli.manifest import DataType


class PostAPI(Protocol):
    def post(
        self,
        url: str,
        data: dict[str, Any],
        files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
    ) -> Any: ...


class FileTransferHandler(ABC):
    """Abstract base class for file transfer handlers."""

    def __init__(self, api: PostAPI) -> None:
        self._api = api

    @abstractmethod
    def send_file(
        self,
        path: Path,
        uuid: uuid.UUID,
        file_type: str,
        sim_data: dict[str, Any],
        chunk_size: int,
        log_stream: IO[str],
        type: DataType,
    ): ...
