import gzip
import io
import json
import shutil
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, override

from simdb.cli.manifest import DataType
from simdb.json import CustomEncoder
from simdb.remote.models import ChunkInfo

from . import FileTransferHandler, PostAPI

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage

    from simdb.database.models import File as SimFile


def _read_bytes_in_chunks(
    path: Path, compressed: bool = True, chunk_size: int = 1024
) -> Iterable[bytes]:
    with path.open("rb") as file_in:
        while True:
            if compressed:
                with io.BytesIO() as buffer:
                    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz_file:
                        data = file_in.read(chunk_size)
                        if not data:
                            break
                        _ = gz_file.write(data)
                    _ = buffer.seek(0)
                    yield buffer.read()
            else:
                data = file_in.read(chunk_size)
                if not data:
                    break
                yield data


def save_chunked_file(
    file: "FileStorage",
    chunk_info: ChunkInfo,
    path: Path,
    compressed: bool = True,
) -> None:
    """Write a single uploaded chunk to its target path on disk.

    The chunk is decompressed from gzip when *compressed* is ``True`` (the
    default).  The file is created if it does not yet exist; otherwise it is
    opened for random-write so that each chunk lands at the correct offset.
    """
    with path.open("r+b" if path.exists() else "wb") as file_out:
        file_out.seek(chunk_info.chunk_size * chunk_info.chunk)
        if compressed:
            with gzip.GzipFile(fileobj=file.stream, mode="rb") as gz_file:
                file_out.write(gz_file.read())
        else:
            file_out.write(file.stream.read())


def stage_file_from_chunks(
    files: "Iterable[FileStorage]",
    chunk_info: dict[str, ChunkInfo],
    sim_files: "list[SimFile]",
    common_root: Path | None,
    staging_dir: Path,
) -> None:
    """Stage a set of uploaded file chunks into *staging_dir*.

    Each entry in *files* is matched against *sim_files* by UUID, written to
    the correct byte offset within the reconstructed file via
    :func:`save_chunked_file`, and assembled in place.  *staging_dir* (which
    should already include the simulation-UUID path component) is created if
    it does not yet exist.
    """
    # Lazy import: secure_path depends on werkzeug, a server-only package.
    from simdb.remote.core.path import secure_path

    staging_dir.mkdir(parents=True, exist_ok=True)

    found_files = []
    for file in files:
        if file.filename:
            file_uuid = uuid.UUID(file.filename)
            sim_file = next((f for f in sim_files if f.uuid == file_uuid), None)
            if sim_file is None:
                raise ValueError(f"file with uuid {file_uuid} not found in simulation")
            if sim_file.uri.scheme != "file":
                raise ValueError("cannot upload non file URI")
            found_files.append((file, sim_file))

    for file, sim_file in found_files:
        path = secure_path(Path(sim_file.uri.path), common_root, staging_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_chunk_info = chunk_info.get(
            sim_file.uuid.hex, ChunkInfo(chunk_size=0, chunk=0, num_chunks=1)
        )
        save_chunked_file(file, file_chunk_info, path)


class HttpFileTransferHandler(FileTransferHandler):
    def __init__(self, api: PostAPI) -> None:
        super().__init__(api)

    def _send_chunk(
        self,
        chunk_index: int,
        chunk: bytes,
        chunk_size: int,
        file_uuid: uuid.UUID,
        file_type: str,
        sim_data: dict,
    ) -> None:
        data = {
            "simulation": sim_data,
            "file_type": file_type,
            "chunk_info": {
                file_uuid.hex: {"chunk_size": chunk_size, "chunk": chunk_index}
            },
        }
        files: list[tuple[str, tuple[str, bytes, str]]] = [
            (
                "data",
                (
                    "data",
                    json.dumps(data, cls=CustomEncoder).encode(),
                    "text/json",
                ),
            ),
            ("files", (file_uuid.hex, chunk, "application/octet-stream")),
        ]
        self._api.post("files", data={}, files=files)

    @override
    def send_file(
        self,
        path: Path,
        uuid: uuid.UUID,
        file_type: str,
        sim_data: dict[str, Any],
        chunk_size: int,
        log_stream: IO[str],
        type: DataType,
    ) -> None:
        msg = f"Uploading file {path} "
        print(msg, file=log_stream, end="")
        num_chunks = 0
        for chunk_index, chunk in enumerate(
            _read_bytes_in_chunks(path, compressed=True, chunk_size=chunk_size)
        ):
            print(".", file=log_stream, end="", flush=True)
            self._send_chunk(chunk_index, chunk, chunk_size, uuid, file_type, sim_data)
            num_chunks += 1
        if num_chunks == 0:
            # empty file
            self._send_chunk(0, b"", chunk_size, uuid, file_type, sim_data)
        if type == DataType.FILE:
            self._api.post(
                "files",
                data={
                    "simulation": sim_data,
                    "obj_type": DataType.FILE,
                    "files": [
                        {
                            "chunks": num_chunks,
                            "file_type": file_type,
                            "file_uuid": uuid.hex,
                            "ids_list": None,
                        }
                    ],
                },
            )
        print(f"\r{msg}", file=log_stream, end="")
        print(
            "Complete".rjust(shutil.get_terminal_size().columns - len(msg)),
            file=log_stream,
            flush=True,
        )
