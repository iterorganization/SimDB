import gzip
import io
import json
import shutil
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import IO, Any, override

from simdb.cli.manifest import DataType
from simdb.json import CustomEncoder

from . import FileTransferHandler, PostAPI


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
