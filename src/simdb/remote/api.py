import os
import json
import itertools
from pathlib import Path
from flask import g, Blueprint, request, jsonify, Response, current_app, _app_ctx_stack
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from functools import wraps
import uuid
import gzip
from typing import List, Iterable, Dict
from itertools import chain

from .. import __version__
from ..database import Database, DatabaseError
from ..database.models import Simulation, File, Watcher
from ..checksum import sha1_checksum
from ..cli.manifest import DataObject

api = Blueprint("api", __name__)


def check_auth(username, password, user):
    """This function is called to check if a username / password combination is valid.
    """
    if user and username != user:
        return False

    if username == "test" and password == "test":
        return True

    if username == "admin" and password == current_app.config["ADMIN_PASSWORD"]:
        return True

    return False


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response("Could not verify your access level for that URL. You have to login with proper credentials",
                    401, {"WWW-Authenticate": "Basic realm='Login Required'"})


class RequiresAuth:

    def __init__(self, user=None):
        self.user = user

    def __call__(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password, self.user):
                return authenticate()
            return f(*args, **kwargs)
        return decorated


def requires_auth(*args):
    return RequiresAuth(*args)


def error(message: str) -> Response:
    response = jsonify(error=message)
    response.status_code = 500
    return response


@api.record
def setup_db(setup_state):
    app = setup_state.app

    if app.config["DB_TYPE"] == "pgsql":
        api.db = Database(Database.DBMS.POSTGRESQL,
                          scopefunc=_app_ctx_stack.__ident_func__,
                          host=app.config["DB_HOST"], port=app.config["DB_PORT"])
    elif app.config["DB_TYPE"] == "sqlite":
        import appdirs
        db_dir = appdirs.user_data_dir('simdb')
        os.makedirs(db_dir, exist_ok=True)
        api.db = Database(Database.DBMS.SQLITE,
                          scopefunc=_app_ctx_stack.__ident_func__,
                          file=os.path.join(db_dir, "remote.db"))
    else:
        raise RuntimeError("Unknown DB_TYPE in app.cfg: " + app.config["DB_TYPE"])


@api.teardown_request
def remove_db_session(error):
    if api.db:
        api.db.remove()


@api.route("/")
@requires_auth()
def index():
    return jsonify({"api": "simdb", "version": __version__})


@api.route("/reset", methods=["POST"])
@requires_auth("admin")
def reset_db():
    api.db.reset()
    return jsonify({})


@api.route("/simulations", methods=["GET"])
@requires_auth()
def list_simulations():
    if not request.args:
        simulations = api.db.list_simulations()
    else:
        equals = {}
        contains = {}
        for name in request.args:
            value = request.args[name]
            if value.startswith('in:'):
                contains[name] = value.replace('in:', '')
            else:
                equals[name] = value

        simulations = api.db.query_meta(equals, contains)

    return jsonify([sim.data(recurse=True) for sim in simulations])


@api.route("/files", methods=["GET"])
@requires_auth()
def list_files():
    files = api.db.list_files()
    return jsonify([file.data() for file in files])


@api.route("/file/<string:file_uuid>", methods=["GET"])
@requires_auth()
def get_file(file_uuid: str):
    try:
        file = api.db.get_file(file_uuid)
        return jsonify(file.data(recurse=True))
    except DatabaseError as err:
        return error(str(err))


def _save_chunked_file(file: FileStorage, chunk_info: Dict, path: str, compressed: bool=True):
    with open(path, "r+b" if os.path.exists(path) else "wb") as file_out:
        file_out.seek(chunk_info['chunk_size'] * chunk_info['chunk'])
        if compressed:
            with gzip.GzipFile(fileobj=file, mode="rb") as gz_file:
                file_out.write(gz_file.read())
        else:
            file_out.write(file.stream.read())


def _stage_file_from_chunks(files: Iterable[FileStorage], chunk_info: Dict, sim_uuid: uuid.UUID, sim_files: List[File]) -> None:
    staging_dir = Path(current_app.config["UPLOAD_FOLDER"]) / sim_uuid.hex
    os.makedirs(staging_dir, exist_ok=True)

    for file in files:
        if file.filename:
            file_uuid = uuid.UUID(file.filename)
            sim_file = next((f for f in sim_files if f.uuid == file_uuid), None)
            if sim_file is None:
                raise ValueError("file with uuid %s not found in simulation" % file_uuid)
            file_name = secure_filename(str(sim_file.uri.path))
            path = staging_dir / file_name
            file_chunk_info = chunk_info.get(sim_file.uuid.hex, {'chunk_size': 0, 'chunk': 0, 'num_chunks': 1})
            _save_chunked_file(file, file_chunk_info, path)


def _set_alias(alias: str):
    character = None
    if alias.endswith('-'):
        character = '-'
    elif alias.endswith('#'):
        character = '#'

    if not character:
        return (None, -1)

    next_id = 1
    aliases = api.db.get_aliases(alias)
    for existing_alias in aliases:
        existing_id = int(existing_alias.split(character)[1])
        if next_id <= existing_id:
            next_id = existing_id + 1
    alias = '%s%d' % (alias, next_id)

    return alias, next_id


def _verify_files(file_uuid: uuid.UUID, sim_uuid: uuid.UUID, sim_files: List[File]):
    staging_dir = Path(current_app.config["UPLOAD_FOLDER"]) / sim_uuid.hex
    sim_file = next((f for f in sim_files if f.uuid == file_uuid), None)
    if sim_file is None:
        raise ValueError("file with uuid %s not found in simulation" % file_uuid)
    if sim_file.type == DataObject.Type.FILE:
        file_name = secure_filename(str(sim_file.uri.path))
        path = staging_dir / file_name
        if not path.exists():
            raise ValueError('file %s does not exist' % path)
        checksum = sha1_checksum(path)
        if sim_file.checksum != checksum:
            raise ValueError("checksum failed for file %s" % repr(sim_file))
    elif sim_file.type == DataObject.Type.IMAS:
        from ..imas.checksum import checksum as imas_checksum
        checksum = imas_checksum(sim_file.uri)
        if sim_file.checksum != checksum:
            raise ValueError("checksum failed for IDS %s" % sim_file.uri)


@api.route("/files", methods=["POST"])
@requires_auth()
def upload_file():
    try:
        data = request.get_json()
        if data:
            simulation = Simulation.from_data(data["simulation"])
            for file in data['files']:
                file_uuid = uuid.UUID(file['file_uuid'])
                file_type = file['file_type']
                sim_files = simulation.inputs if file_type == 'input' else simulation.outputs
                _verify_files(file_uuid, simulation.uuid, sim_files)
            return jsonify({})

        data = json.load(request.files["data"])

        if "simulation" not in data:
            return error("Simulation data not provided")

        simulation = Simulation.from_data(data["simulation"])
        simulation.alias = simulation.uuid.hex[0:8]

        chunk_info = data.get("chunk_info", {})
        file_type = data['file_type']

        files = request.files.getlist("files")
        if not files:
            return error("No files given")

        sim_files = simulation.inputs if file_type == 'input' else simulation.outputs
        _stage_file_from_chunks(files, chunk_info, simulation.uuid, sim_files)

        return jsonify({})
    except ValueError as err:
        return error(str(err))


@api.route("/simulations", methods=["POST"])
@requires_auth()
def ingest_simulation():
    try:
        data = request.get_json()

        if "simulation" not in data:
            return error("Simulation data not provided")

        simulation = Simulation.from_data(data["simulation"])
        simulation.alias = simulation.uuid.hex[0:8]

        staging_dir = Path(current_app.config["UPLOAD_FOLDER"]) / simulation.uuid.hex

        for sim_file in chain(simulation.inputs, simulation.outputs):
            file_name = secure_filename(str(sim_file.uri.path))
            path = staging_dir / file_name
            if not path.exists():
                raise ValueError('simulation file %s not uploaded' % sim_file.uuid)
            sim_file.directory = staging_dir

        api.db.insert_simulation(simulation)

        return jsonify({})
    except (DatabaseError, ValueError) as err:
        return error(str(err))


@api.route("/simulation/<string:sim_id>", methods=["GET"])
@requires_auth()
def get_simulation(sim_id: str):
    try:
        simulation = api.db.get_simulation(sim_id)
        return jsonify(simulation.data(recurse=True))
    except DatabaseError as err:
        return error(str(err))


@api.route("/staging_dir/<string:sim_hex>", methods=["GET"])
@requires_auth()
def get_staging_dir(sim_hex: str):
    staging_dir = Path(current_app.config["UPLOAD_FOLDER"]) / sim_hex
    os.makedirs(staging_dir, exist_ok=True)
    return jsonify({'staging_dir': str(staging_dir)})


@api.route("/simulation/<string:sim_id>", methods=["DELETE"])
@requires_auth("admin")
def delete_simulation(sim_id: str):
    try:
        simulation = api.db.delete_simulation(sim_id)
        files = []
        for file in itertools.chain(simulation.inputs, simulation.outputs):
            files.append("%s (%s)" % (file.uuid, file.file_name))
            os.remove(os.path.join(file.directory, file.file_name))
        if simulation.inputs or simulation.outputs:
            dir = simulation.inputs[0].directory if simulation.inputs else simulation.outputs[0].directory
            os.rmdir(simulation.inputs[0].directory)
        return jsonify({"deleted": {"simulation": simulation.uuid, "files": files}})
    except DatabaseError as err:
        return error(str(err))


@api.route("/publish/<string:sim_id>", methods=["POST"])
@requires_auth()
def publish_simulation(sim_id: str):
    try:
        simulation = api.db.get_simulation(sim_id)
        return error("not yet implemented")
    except DatabaseError as err:
        return error(str(err))


@api.route("/watchers/<string:sim_id>", methods=["POST"])
@requires_auth()
def add_watcher(sim_id: str):
    try:
        data = request.get_json()

        if "user" not in data:
            return error("Watcher username not provided")
        if "email" not in data:
            return error("Watcher email not provided")
        if "notification" not in data:
            return error("Watcher notification not provided")

        watcher = Watcher(data["user"], data["email"], data["notification"])
        api.db.add_watcher(sim_id, watcher)
        return jsonify({"added": {"simulation": sim_id, "watcher": data["user"]}})
    except DatabaseError as err:
        return error(str(err))


@api.route("/watchers/<string:sim_id>", methods=["DELETE"])
@requires_auth()
def remove_watcher(sim_id: str):
    try:
        data = request.get_json()

        if "user" not in data:
            return error("Watcher username not provided")

        api.db.remove_watcher(sim_id, data["user"])
        return jsonify({"removed": {"simulation": sim_id, "watcher": data["user"]}})
    except DatabaseError as err:
        return error(str(err))


@api.route("/watchers/<string:sim_id>", methods=["GET"])
@requires_auth()
def list_watchers(sim_id: str):
    try:
        return jsonify([watcher.data(recurse=True) for watcher in api.db.list_watchers(sim_id)])
    except DatabaseError as err:
        return error(str(err))


@api.route("/validation_schema", methods=["GET"])
@requires_auth()
def get_validation_schema():
    from ..validation.validator import Validator
    return jsonify(Validator.validation_schema())
