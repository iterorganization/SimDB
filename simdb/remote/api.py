import os
import json
import itertools
from flask import g, Blueprint, request, jsonify, Response, current_app
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from functools import wraps
import uuid
import gzip
from typing import List

from .. import __version__
from ..database.database import Database, DatabaseError
from ..database.models import Simulation, File
from ..checksum import sha1_checksum

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


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def error(message: str) -> Response:
    response = jsonify(error=message)
    response.status_code = 500
    return response


def get_db() -> Database:
    if not hasattr(g, 'db'):
        if current_app.config["DB_TYPE"] == "pgsql":
            g.db = Database(Database.DBMS.POSTGRESQL,
                            host=current_app.config["DB_HOST"], port=current_app.config["DB_PORT"])
        elif current_app.config["DB_TYPE"] == "sqlite":
            import appdirs
            db_dir = appdirs.user_data_dir('simdb')
            os.makedirs(db_dir, exist_ok=True)
            g.db = Database(Database.DBMS.SQLITE, file=os.path.join(db_dir, "remote.db"))
        else:
            raise RuntimeError("Unkown DB_TYPE in app.cfg: " + current_app.config["DB_TYPE"])
    return g.db


@api.route("/")
@requires_auth
def index():
    return jsonify({"api": "simdb", "version": __version__})


@api.route("/reset", methods=["POST"])
@requires_auth("admin")
def reset_db():
    get_db().reset()
    return jsonify({})


@api.route("/simulations", methods=["GET"])
@requires_auth
def list_simulations():
    if not request.args:
        simulations = get_db().list_simulations()
    else:
        equals = {}
        contains = {}
        for name in request.args:
            value = request.args[name]
            if value.startswith('in:'):
                contains[name] = value.replace('in:', '')
            else:
                equals[name] = value

        simulations = get_db().query_meta(equals, contains)

    return jsonify([sim.data(recurse=True) for sim in simulations])


@api.route("/files", methods=["GET"])
@requires_auth
def list_files():
    files = get_db().list_files()
    return jsonify([file.data() for file in files])


@api.route("/file/<string:file_uuid>", methods=["GET"])
@requires_auth
def get_file(file_uuid):
    try:
        file = get_db().get_file(file_uuid)
        return jsonify(file.data(recurse=True))
    except DatabaseError as err:
        return error(str(err))


def save_file(file, path: str, compressed: bool=True):
    if compressed:
        with gzip.GzipFile(fileobj=file, mode="rb") as gzfile:
            with open(path, "wb") as file:
                file.write(gzfile.read())
    else:
        file.save(path)


def _stage_files(files: List[FileStorage], uuid_hex: str, sim_files: List[File]) -> None:
    staging_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], uuid_hex)
    os.makedirs(staging_dir, exist_ok=True)

    for file in files:
        if file.filename:
            file_uuid = uuid.UUID(file.filename)
            if sum(1 if x.uuid == file_uuid else 0 for x in sim_files) == 0:
                raise ValueError("file with uuid %s not found in simulation" % file_uuid.hex)
            sim_file = next(filter(lambda x: x.uuid == file_uuid, sim_files))
            file_name = secure_filename(sim_file.file_name)
            path = os.path.join(staging_dir, file_name)
            save_file(file, path)
            checksum = sha1_checksum(path)
            if sim_file.checksum != checksum:
                raise ValueError("checksum failed for file %s" % repr(sim_file))
            sim_file.directory = staging_dir


@api.route("/simulations", methods=["PUT"])
@requires_auth
def ingest_simulation():
    data = json.loads(request.files["data"].read())

    if "simulation" not in data:
        return error("Simulation data not provided")

    simulation = Simulation.from_data(data["simulation"])
    simulation.alias = simulation.uuid.hex[0:8]

    try:
        if "inputs" in request.files:
            files = request.files.getlist("inputs")
            _stage_files(files, simulation.uuid.hex, simulation.inputs)

        if "outputs" in request.files:
            files = request.files.getlist("outputs")
            _stage_files(files, simulation.uuid.hex, simulation.outputs)

        get_db().insert_simulation(simulation)
        return jsonify({})
    except (DatabaseError, ValueError) as err:
        return error(str(err))


@api.route("/simulation/<string:sim_id>", methods=["GET"])
@requires_auth
def get_simulation(sim_id):
    try:
        simulation = get_db().get_simulation(sim_id)
        return jsonify(simulation.data(recurse=True))
    except DatabaseError as err:
        return error(str(err))


@api.route("/simulation/<string:sim_id>", methods=["DELETE"])
@requires_auth("admin")
def delete_simulation(sim_id):
    try:
        simulation = get_db().delete_simulation(sim_id)
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
@requires_auth
def publish_simulation(sim_id):
    try:
        simulation = get_db().get_simulation(sim_id)
        return error("not yet implemented")
    except DatabaseError as err:
        return error(str(err))
