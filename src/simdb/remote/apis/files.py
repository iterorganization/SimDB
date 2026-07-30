import gzip
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import magic
from flask import Response, jsonify, request, send_file
from flask_restx import Namespace, Resource
from werkzeug.datastructures import FileStorage

from simdb.checksum import sha1_checksum
from simdb.cli.manifest import DataType
from simdb.database import DatabaseError, models
from simdb.imas.checksum import checksum as imas_checksum
from simdb.imas.utils import SimDBUrl, imas_files
from simdb.remote.core.auth import User, requires_auth
from simdb.remote.core.errors import error
from simdb.remote.core.path import find_common_root, secure_path
from simdb.remote.core.pydantic_utils import pydantic_validate
from simdb.remote.core.typing import current_app
from simdb.remote.models import (
    ChunkInfo,
    FileDataList,
    FileGetDataResponse,
    FileRegistrationData,
    FileUploadData,
)

api = Namespace("files", path="/")


def _verify_file(
    sim_uuid: uuid.UUID,
    sim_file: models.File,
    common_root: Optional[Path],
    ids_list: Optional[list] = None,
):
    if current_app.simdb_config.get_option(
        "development.disable_checksum", default=False
    ):
        return
    staging_dir = (
        Path(current_app.simdb_config.get_string_option("server.upload_folder"))
        / sim_uuid.hex
    )
    if sim_file.type == DataType.FILE:
        if sim_file.uri.path is None:
            raise ValueError("File does not have an associated path")
        path = secure_path(Path(sim_file.uri.path), common_root, staging_dir)
        if not path.exists():
            raise ValueError(f"file {path} does not exist")
        checksum = sha1_checksum(SimDBUrl.build(scheme="file", path=path.as_posix()))
        if sim_file.checksum != checksum:
            raise ValueError(f"checksum failed for file {sim_file!r}")
    elif sim_file.type == DataType.IMAS:
        uri = sim_file.uri
        qs = dict(uri.query_params())
        path_value = qs.get("path")
        if path_value is None:
            raise ValueError("The 'path' key is missing in the URI query")
        if common_root == Path("/"):
            path_value = str(staging_dir) + path_value
        elif common_root is not None and common_root == path_value:
            path_value = path_value.replace(str(common_root), str(staging_dir))

        else:
            path_value = str(staging_dir)
        new_uri = uri.build(
            scheme=uri.scheme, path=uri.path, query=f"path={path_value}"
        )
        checksum = imas_checksum(new_uri, ids_list or [])
        if sim_file.checksum != checksum:
            raise ValueError(f"checksum failed for simulation {sim_file.uri}")


def _save_chunked_file(
    file: FileStorage, chunk_info: ChunkInfo, path: Path, compressed: bool = True
):
    with path.open("r+b" if path.exists() else "wb") as file_out:
        file_out.seek(chunk_info.chunk_size * chunk_info.chunk)
        if compressed:
            with gzip.GzipFile(fileobj=file.stream, mode="rb") as gz_file:
                file_out.write(gz_file.read())
        else:
            file_out.write(file.stream.read())


def _stage_file_from_chunks(
    files: Iterable[FileStorage],
    chunk_info: Dict[str, ChunkInfo],
    sim_uuid: uuid.UUID,
    sim_files: List[models.File],
    common_root: Optional[Path],
) -> None:
    staging_dir = (
        Path(current_app.simdb_config.get_string_option("server.upload_folder"))
        / sim_uuid.hex
    )
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
        _save_chunked_file(file, file_chunk_info, path)


def _check_file_is_in_simulation(
    simulation: models.Simulation, file_uuid: uuid.UUID, file_type: str
) -> models.File:
    sim_files = simulation.inputs if file_type == "input" else simulation.outputs
    sim_file = next((f for f in sim_files if f.uuid == file_uuid), None)
    if sim_file is None:
        raise ValueError(f"file with uuid {file_uuid} not found in simulation")
    return sim_file


def _process_simulation_data(body: FileRegistrationData) -> Response:
    simulation = models.Simulation.from_data_model(body.simulation)
    sim_file_paths = simulation.file_paths()
    common_root = find_common_root(sim_file_paths)

    if body.obj_type == DataType.FILE:
        for file in body.files:
            sim_file = _check_file_is_in_simulation(
                simulation, file.file_uuid, file.file_type
            )
            _verify_file(simulation.uuid, sim_file, common_root)
    elif body.obj_type == DataType.IMAS:
        file = body.files[0]
        sim_files = (
            simulation.inputs if file.file_type == "input" else simulation.outputs
        )
        sim_file = next(f for f in sim_files if f.uuid == file.file_uuid)
        _verify_file(simulation.uuid, sim_file, common_root, file.ids_list)
    else:
        raise ValueError(f"Unsupported object type {body.obj_type}")

    return jsonify({})


def _handle_file_upload() -> Response:
    body = FileUploadData.model_validate_json(request.files["data"].stream.read())

    simulation = models.Simulation.from_data_model(body.simulation)

    files = request.files.getlist("files")
    if not files:
        return error("No files given")

    sim_file_paths = simulation.file_paths()
    common_root = find_common_root(sim_file_paths)

    sim_files = simulation.inputs if body.file_type == "input" else simulation.outputs
    _stage_file_from_chunks(
        files, body.chunk_info or {}, simulation.uuid, sim_files, common_root
    )

    return jsonify({})


@api.route("/files")
class FileList(Resource):
    @requires_auth()
    @pydantic_validate(api)
    def get(self, user: User) -> FileDataList:
        """List all registered files.

        Returns every input and output file known to the database across all
        simulations.
        """
        files = current_app.db.list_files()
        return FileDataList.model_validate([file.to_model() for file in files])

    @requires_auth()
    def post(self, user: User):
        """Register or upload simulation files.

        Handles two content types. A JSON body registers file metadata and
        verifies each file's checksum against the copy already present in the
        simulation's staging directory. A multipart form upload streams file
        content (optionally gzip-compressed and chunked) into the staging
        directory ahead of registration.
        """
        try:
            if request.is_json:
                body = FileRegistrationData.model_validate_json(request.get_data())
                return _process_simulation_data(body)
            return _handle_file_upload()

        except ValueError as err:
            return error(str(err))


@api.route("/file/<string:file_uuid>")
class File(Resource):
    @requires_auth()
    @pydantic_validate(api)
    def get(self, file_uuid: str, user: Optional[User] = None) -> FileGetDataResponse:
        """Retrieve a single file's metadata.

        Returns the stored record for the file identified by ``file_uuid``,
        including its resolved on-disk path.
        """
        file = current_app.db.get_file(file_uuid)
        return file.to_model_with_path()


@api.route("/file/download/<string:file_uuid>")
class NonIMASFileDownload(Resource):
    @requires_auth()
    def get(self, file_uuid: str, user: Optional[User] = None):
        """Download a non-IMAS file.

        Streams the raw contents of the plain (non-IMAS) file identified by
        ``file_uuid`` back to the client, with a MIME type inferred from the
        file itself.
        """
        try:
            file: models.File = current_app.db.get_file(file_uuid)
            if file.type != DataType.FILE:
                return error("Invalid file type for download")
            if file.uri.path is None:
                return error("File path is not set")
            mimetype = magic.from_file(file.uri.path, mime=True)
            return send_file(file.uri.path, mimetype=mimetype)
        except DatabaseError as err:
            return error(str(err))


@api.route("/file/download/<string:file_uuid>/<int:file_index>")
class FileDownload(Resource):
    @requires_auth()
    def get(self, file_uuid: str, file_index: int, user: Optional[User] = None):
        """Download one file from a file entry by index.

        Streams a single physical file back to the client. For a plain file
        only index ``0`` is valid. For an IMAS entry, which maps to several
        physical files, ``file_index`` selects which one to download.
        """
        try:
            file: models.File = current_app.db.get_file(file_uuid)
            if file.type == DataType.FILE:
                if file_index != 0:
                    return error(f"invalid file_index for file {file.uri}")
                if file.uri.path is None:
                    return error("File path is not set")
                mimetype = magic.from_file(file.uri.path, mime=True)
                return send_file(file.uri.path, mimetype=mimetype)
            else:
                file: models.File = current_app.db.get_file(file_uuid)
                paths = imas_files(file.uri)

                if file_index < 0 or file_index >= len(paths):
                    return error(f"invalid file_index for file {file.uri}")

                path = paths[file_index]
                mimetype = magic.from_file(path, mime=True)
                return send_file(path, mimetype=mimetype)
        except DatabaseError as err:
            return error(str(err))
