"""Rclone-backed file transfer handler for the SimDB CLI.

When the server advertises ``RCLONE`` as an available transfer type, it
supplies a ``[file_transfer "rclone"]`` config section whose key/value pairs
are forwarded verbatim to :class:`RcloneFileTransferHandler` as keyword
arguments.  A minimal server-side config looks like::

    [file_transfer "rclone"]
    remote = sftp_server:/simdb/staging

The *remote* value must be any rclone destination that the CLI machine can
reach (e.g. ``s3:my-bucket/simdb``, ``sftp_server:/data/staging``).  The
handler copies each file to ``{remote}/{sim_uuid}/{filename}`` via
``rclone copyto``, mirroring the per-simulation staging layout used by the
HTTP handler.  The server is expected to be configured so that it can read
from the same rclone destination (e.g. by mounting it or using rclone on the
server side).
"""

import shutil
import subprocess
import uuid as _uuid_mod
from pathlib import Path
from typing import IO, Any, override

from simdb.cli.manifest import DataType

from . import FileTransferHandler, PostAPI


class RcloneFileTransferHandler(FileTransferHandler):
    """File transfer handler that delegates uploads to ``rclone``.

    Accepts the transfer options supplied by the server and uses them to
    construct the rclone destination for every file sent.

    :param api: the remote API, used to register files after each transfer.
    :param remote: rclone destination prefix as configured on the server,
        e.g. ``"sftp_server:/simdb/staging"`` or ``"s3:bucket/simdb"``.
        A trailing slash is normalised away.
    """

    def __init__(self, api: PostAPI, remote: str) -> None:
        super().__init__(api)
        self._remote = remote.rstrip("/")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _dest_path(self, sim_data: dict[str, Any], filename: str) -> str:
        """Return the fully-qualified rclone destination for *filename*.

        Files are staged under ``{remote}/{sim_uuid_hex}/{filename}`` so that
        all files belonging to a simulation share a single directory on the
        remote, matching the layout the HTTP handler creates on the server.
        """
        sim_uuid_hex = str(sim_data["uuid"]).replace("-", "")
        return f"{self._remote}/{sim_uuid_hex}/{filename}"

    def _run_rclone(self, source: Path, dest: str, log_stream: IO[str]) -> None:
        """Run ``rclone copyto <source> <dest>`` and forward output to *log_stream*.

        Any output written to stderr by rclone (warnings, stats, etc.) is
        echoed to *log_stream* line by line.  A non-zero exit code raises a
        :class:`RuntimeError` that includes the captured stderr.

        :param source: local file path to upload.
        :param dest: fully-qualified rclone destination path.
        :param log_stream: stream used for user-facing progress messages.
        :raises RuntimeError: if rclone exits with a non-zero return code.
        """
        proc = subprocess.Popen(
            ["rclone", "copyto", str(source), dest],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        _, stderr = proc.communicate()

        for line in stderr.splitlines():
            print(line, file=log_stream, flush=True)

        if proc.returncode != 0:
            msg = (
                f"rclone exited with code {proc.returncode}"
                f" while copying {source!s} to {dest}"
            )
            raise RuntimeError(msg)

    # ------------------------------------------------------------------
    # FileTransferHandler interface
    # ------------------------------------------------------------------

    @override
    def send_file(
        self,
        path: Path,
        uuid: _uuid_mod.UUID,
        file_type: str,
        sim_data: dict[str, Any],
        log_stream: IO[str],
        type: DataType,
    ) -> None:
        """Transfer *path* to the rclone remote and, for file-typed data,
        register it with the server.

        IMAS registration is handled by ``RemoteAPI._send_file`` after all
        component paths are transferred; this method only needs to register
        :attr:`~simdb.cli.manifest.DataType.FILE`-typed entries.

        :param path: local path of the file to upload.
        :param uuid: UUID of the file record on the server.
        :param file_type: ``"input"`` or ``"output"``.
        :param sim_data: serialised simulation dict passed to the server for
            registration.
        :param log_stream: stream used for user-facing progress messages.
        :param type: data type of the file (``FILE`` or ``IMAS``).
        :raises RuntimeError: if the underlying rclone process fails.
        """
        path = Path(path)
        dest = self._dest_path(sim_data, path.name)

        msg = f"Uploading file {path} "
        print(msg, file=log_stream, end="", flush=True)

        self._run_rclone(path, dest, log_stream)

        if type == DataType.FILE:
            self._api.post(
                "files",
                data={
                    "simulation": sim_data,
                    "obj_type": DataType.FILE,
                    "files": [
                        {
                            "chunks": 0,
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
