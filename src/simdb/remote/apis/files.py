from flask import request, jsonify, send_file, Response, stream_with_context
from flask_restx import Resource, Namespace
from typing import Optional, List, Iterable, Dict
from pathlib import Path
from werkzeug.datastructures import FileStorage
import os
import uuid
import json
import gzip
import itertools
import magic

from ..core.typing import current_app
from ...remote.core.auth import User, requires_auth
from ...remote.core.path import find_common_root, secure_path
from ...remote.core.errors import error
from ...database import DatabaseError, models
from ...cli.manifest import DataObject
from ...checksum import sha1_checksum
from ...uri import URI

api = Namespace("files", path="/")


def _verify_file(
    sim_uuid: uuid.UUID, sim_file: models.File, common_root: Optional[Path]
):
    if current_app.simdb_config.get_option(
        "development.disable_checksum", default=False
    ):
        return
    staging_dir = (
        Path(current_app.simdb_config.get_option("server.upload_folder")) / sim_uuid.hex
    )
    if sim_file.type == DataObject.Type.FILE:
        path = secure_path(sim_file.uri.path, common_root, staging_dir)
        if not path.exists():
            raise ValueError("file %s does not exist" % path)
        checksum = sha1_checksum(URI(scheme="file", path=path))
        if sim_file.checksum != checksum:
            raise ValueError(f"checksum failed for file {sim_file!r}")
    elif sim_file.type == DataObject.Type.IMAS:
        from ...imas.checksum import checksum as imas_checksum        
        uri = sim_file.uri
        uri.query.set("path", str(staging_dir));
        checksum = imas_checksum(uri)
        if sim_file.checksum != checksum:
            raise ValueError("checksum failed for IDS %s" % uri)


def _save_chunked_file(
    file: FileStorage, chunk_info: Dict, path: Path, compressed: bool = True
):
    with open(path, "r+b" if path.exists() else "wb") as file_out:
        file_out.seek(chunk_info["chunk_size"] * chunk_info["chunk"])
        if compressed:
            with gzip.GzipFile(fileobj=file, mode="rb") as gz_file:
                file_out.write(gz_file.read())
        else:
            file_out.write(file.stream.read())


def _stage_file_from_chunks(
    files: Iterable[FileStorage],
    chunk_info: Dict,
    sim_uuid: uuid.UUID,
    sim_files: List[models.File],
    common_root: Optional[Path],
) -> None:
    staging_dir = (
        Path(current_app.simdb_config.get_option("server.upload_folder")) / sim_uuid.hex
    )
    os.makedirs(staging_dir, exist_ok=True)

    found_files = []
    for file in files:
        if file.filename:
            file_uuid = uuid.UUID(file.filename)
            sim_file = next((f for f in sim_files if f.uuid == file_uuid), None)
            if sim_file is None:
                raise ValueError(
                    "file with uuid %s not found in simulation" % file_uuid
                )
            if sim_file.uri.scheme != "file":
                raise ValueError("cannot upload non file URI")
            found_files.append((file, sim_file))

    for file, sim_file in found_files:
        path = secure_path(sim_file.uri.path, common_root, staging_dir)
        os.makedirs(path.parent, exist_ok=True)
        file_chunk_info = chunk_info.get(
            sim_file.uuid.hex, {"chunk_size": 0, "chunk": 0, "num_chunks": 1}
        )
        _save_chunked_file(file, file_chunk_info, path)


def _check_file_is_in_simulation(
    simulation: models.Simulation, file_uuid: uuid.UUID, file_type: str
) -> models.File:
    sim_files = simulation.inputs if file_type == "input" else simulation.outputs
    sim_file = next((f for f in sim_files if f.uuid == file_uuid), None)
    if sim_file is None:
        raise ValueError("file with uuid %s not found in simulation" % file_uuid)
    return sim_file


def _process_simulation_data(data: dict) -> Response:
    simulation = models.Simulation.from_data(data["simulation"])
    sim_file_paths = simulation.file_paths()
    common_root = find_common_root(sim_file_paths)
    if DataObject.Type(data["obj_type"]) == DataObject.Type.FILE:
        for file in data["files"]:
            sim_file = _check_file_is_in_simulation(
                simulation, uuid.UUID(file["file_uuid"]), file["file_type"]
            )
            _verify_file(simulation.uuid, sim_file, common_root)
    elif DataObject.Type(data["obj_type"]) == DataObject.Type.IMAS:
        file = data["files"][0]
        sim_files = simulation.inputs if file["file_type"] == "input" else simulation.outputs
        sim_file = next((f for f in sim_files if f.uuid == uuid.UUID(file["file_uuid"])), None)
        _verify_file(simulation.uuid, sim_file, common_root)        
    else:
        raise ValueError("Unsupported object type %s" % data["obj_type"])
    
    return jsonify({})


def _handle_file_upload() -> Response:
    from ...json import CustomDecoder

    data: dict = json.load(request.files["data"], cls=CustomDecoder)

    if "simulation" not in data:
        return error("Simulation data not provided")

    simulation = models.Simulation.from_data(data["simulation"])

    chunk_info = data.get("chunk_info", {})
    file_type = data["file_type"]

    files = request.files.getlist("files")
    if not files:
        return error("No files given")

    sim_file_paths = simulation.file_paths()
    common_root = find_common_root(sim_file_paths)

    sim_files = simulation.inputs if file_type == "input" else simulation.outputs
    _stage_file_from_chunks(files, chunk_info, simulation.uuid, sim_files, common_root)

    return jsonify({})


@api.route("/files")
class FileList(Resource):
    @requires_auth()
    def get(self, user: User):
        files = current_app.db.list_files()
        return jsonify([file.data() for file in files])

    @requires_auth()
    def post(self, user: User):
        try:
            data = request.get_json()
            if data:
                return _process_simulation_data(data)
            return _handle_file_upload()

        except ValueError as err:
            return error(str(err))


@api.route("/file/<string:file_uuid>")
class File(Resource):
    @requires_auth()
    def get(self, file_uuid: str, user: User = Optional[None]):
        try:
            file = current_app.db.get_file(file_uuid)
            data = file.data(recurse=True)
            if file.type == DataObject.Type.FILE:
                data["files"] = [
                    {
                        "path": str(file.uri.path),
                        "checksum": file.checksum,
                    }
                ]
            else:
                from ...imas.utils import imas_files

                data["files"] = [
                    {"path": str(path), "checksum": sha1_checksum(URI(f"file:{path}"))}
                    for path in imas_files(file.uri)
                ]
            return jsonify(data)
        except DatabaseError as err:
            return error(str(err))


@api.route("/file/download/<string:file_uuid>")
class NonIMASFileDownload(Resource):
    @requires_auth()
    def get(self, file_uuid: str, user: User = Optional[None]):
        try:
            file: models.File = current_app.db.get_file(file_uuid)
            if file.type != DataObject.Type.FILE:
                return error("Invalid file type for download")
            mimetype = magic.from_file(file.uri.path, mime=True)
            response = send_file(file.uri.path, mimetype=mimetype)
            return Response(
                stream_with_context(response.iter_content()),
                content_type=response.headers["content-type"],
            )
        except DatabaseError as err:
            return error(str(err))


@api.route("/file/download/<string:file_uuid>/<int:file_index>")
class FileDownload(Resource):
    @requires_auth()
    def get(self, file_uuid: str, file_index: int, user: User = Optional[None]):
        try:
            file: models.File = current_app.db.get_file(file_uuid)
            if file.type == DataObject.Type.FILE:
                if file_index != 0:
                    return error(f"invalid file_index for file {file.uri}")
                mimetype = magic.from_file(file.uri.path, mime=True)
                return send_file(file.uri.path, mimetype=mimetype)
            else:
                from ...imas.utils import imas_files

                file: models.File = current_app.db.get_file(file_uuid)
                paths = imas_files(file.uri)

                if file_index < 0 or file_index >= len(paths):
                    return error(f"invalid file_index for file {file.uri}")

                path = paths[file_index]
                mimetype = magic.from_file(path, mime=True)
                return send_file(path, mimetype=mimetype)
        except DatabaseError as err:
            return error(str(err))
