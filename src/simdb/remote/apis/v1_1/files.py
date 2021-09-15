from flask import request, current_app, jsonify
from flask_restx import Resource, Namespace
from typing import Optional, List, Iterable, Dict
from pathlib import Path
from werkzeug.datastructures import FileStorage
from uri import URI
import os
import uuid
import json
import gzip
import itertools

from simdb.remote.core.auth import User, requires_auth
from simdb.remote.core.path import secure_path
from simdb.remote.core.errors import error
from simdb.database import DatabaseError, models
from simdb.cli.manifest import DataObject
from simdb.checksum import sha1_checksum

api = Namespace('files', path='/')


def _verify_file(sim_uuid: uuid.UUID, sim_file: models.File, common_root: Path):
    if current_app.simdb_config.get_option("development.disable_checksum", default=False):
        return
    staging_dir = Path(current_app.simdb_config.get_option("server.upload_folder")) / sim_uuid.hex
    if sim_file.type == DataObject.Type.FILE:
        path = secure_path(sim_file.uri.path, common_root, staging_dir)
        if not path.exists():
            raise ValueError('file %s does not exist' % path)
        checksum = sha1_checksum(URI(scheme='file', path=path))
        if sim_file.checksum != checksum:
            raise ValueError("checksum failed for file %s" % repr(sim_file))
    elif sim_file.type == DataObject.Type.IMAS:
        from ....imas.checksum import checksum as imas_checksum
        user_folder = current_app.simdb_config.get_option("server.user_upload_folder", default=None)
        uri = sim_file.uri
        if user_folder is not None:
            server_folder = current_app.simdb_config.get_option("server.upload_folder")
            uri.query['path'] = uri.query['path'].replace(str(user_folder), str(server_folder))
        checksum = imas_checksum(uri)
        if sim_file.checksum != checksum:
            raise ValueError("checksum failed for IDS %s" % uri)


def _save_chunked_file(file: FileStorage, chunk_info: Dict, path: Path, compressed: bool = True):
    with open(path, "r+b" if path.exists() else "wb") as file_out:
        file_out.seek(chunk_info['chunk_size'] * chunk_info['chunk'])
        if compressed:
            with gzip.GzipFile(fileobj=file, mode="rb") as gz_file:
                file_out.write(gz_file.read())
        else:
            file_out.write(file.stream.read())


def _stage_file_from_chunks(files: Iterable[FileStorage], chunk_info: Dict, sim_uuid: uuid.UUID,
                            sim_files: List[models.File], common_root: Path) -> None:
    staging_dir = Path(current_app.simdb_config.get_option("server.upload_folder")) / sim_uuid.hex
    os.makedirs(staging_dir, exist_ok=True)

    found_files = []
    for file in files:
        if file.filename:
            file_uuid = uuid.UUID(file.filename)
            sim_file = next((f for f in sim_files if f.uuid == file_uuid), None)
            if sim_file is None:
                raise ValueError("file with uuid %s not found in simulation" % file_uuid)
            if sim_file.uri.scheme != 'file':
                raise ValueError("cannot upload non file URI")
            found_files.append((file, sim_file))

    for file, sim_file in found_files:
        path = secure_path(sim_file.uri.path, common_root, staging_dir)
        os.makedirs(path.parent, exist_ok=True)
        file_chunk_info = chunk_info.get(sim_file.uuid.hex, {'chunk_size': 0, 'chunk': 0, 'num_chunks': 1})
        _save_chunked_file(file, file_chunk_info, path)


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
                simulation = models.Simulation.from_data(data["simulation"])
                for file in data['files']:
                    file_uuid = uuid.UUID(file['file_uuid'])
                    file_type = file['file_type']
                    sim_files = simulation.inputs if file_type == 'input' else simulation.outputs
                    sim_file = next((f for f in sim_files if f.uuid == file_uuid), None)
                    if sim_file is None:
                        raise ValueError("file with uuid %s not found in simulation" % file_uuid)
                    common_root = os.path.commonpath(
                        [f.uri.path for f in itertools.chain(simulation.inputs, simulation.outputs)]
                    )
                    _verify_file(simulation.uuid, sim_file, common_root)
                return jsonify({})

            from ....json import CustomDecoder
            data = json.load(request.files["data"], cls=CustomDecoder)

            if "simulation" not in data:
                return error("Simulation data not provided")

            simulation = models.Simulation.from_data(data["simulation"])

            chunk_info = data.get("chunk_info", {})
            file_type = data['file_type']

            files = request.files.getlist("files")
            if not files:
                return error("No files given")

            all_sim_files = list(itertools.chain(simulation.inputs, simulation.outputs))
            common_root = Path(os.path.commonpath([f.uri.path for f in all_sim_files]))

            sim_files = simulation.inputs if file_type == 'input' else simulation.outputs
            _stage_file_from_chunks(files, chunk_info, simulation.uuid, sim_files, common_root)

            return jsonify({})
        except ValueError as err:
            return error(str(err))


@api.route("/file/<string:file_uuid>")
class File(Resource):

    @requires_auth()
    def get(self, file_uuid: str, user: User = Optional[None]):
        try:
            file = current_app.db.get_file(file_uuid)
            return jsonify(file.data(recurse=True))
        except DatabaseError as err:
            return error(str(err))
