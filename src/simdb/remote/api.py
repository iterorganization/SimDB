import os
import json
import itertools
from pathlib import Path
from flask import Blueprint, request, jsonify, Response, current_app, _app_ctx_stack
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from functools import wraps
import uuid
import gzip
from typing import List, Iterable, Dict, Tuple, Optional
from itertools import chain
from uri import URI
import jwt
import datetime
from collections import namedtuple

from .. import __version__
from ..database import Database, DatabaseError
from ..database.models import Simulation, File, Watcher, MetaData
from ..checksum import sha1_checksum
from ..cli.manifest import DataObject
from ..query import QueryType, parse_query_arg
from .cache import cache

API_VERSION = 1
api = Blueprint("api", __name__)

User = namedtuple("User", ("name", "email"))


def _secure_path(path: Path, common_root: Path, staging_dir: Path) -> Path:
    file_name = secure_filename(path.name)
    directory = staging_dir / path.parent.relative_to(common_root)
    return directory / file_name


def check_role(config, user: User, role: Optional[str]) -> bool:
    config = current_app.simdb_config

    if role:
        import csv

        users = config.get_option(f'role.{role}.users', default='')
        reader = csv.reader([users])
        for row in reader:
            if user in row:
                return True
        return False

    return True


def check_auth(config, username, password) -> Optional[User]:
    """This function is called to check if a username / password combination is valid.
    """
    from easyad import EasyAD

    if username == "admin" and password == config.get_option("server.admin_password"):
        return User("admin", None)

    ad_config = {
        'AD_SERVER': config.get_option('server.ad_server'),
        'AD_DOMAIN': config.get_option('server.ad_domain'),
    }
    ad = EasyAD(ad_config)

    user = ad.authenticate_user(username, password, json_safe=True)
    if user:
        return User(user["sAMAccountName"], user["mail"])
    else:
        return None


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response("Could not verify your access level for that URL. You have to login with proper credentials",
                    401, {"WWW-Authenticate": "Basic realm='Login Required'"})


class RequiresAuth:

    def __init__(self, role=None):
        self._role = role

    def __call__(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            config = current_app.simdb_config
            auth = request.authorization
            user: Optional[User] = None
            if not auth:
                if 'JWT-Token' in request.headers.get('Authorization', ''):
                    try:
                        token = request.headers['Authorization'].split('JWT-Token')[1]
                        payload = jwt.decode(token.strip(), current_app.config.get('SECRET_KEY'), algorithms=['HS256'])
                        expires = datetime.datetime.fromtimestamp(payload['exp'])
                        if datetime.datetime.utcnow() < expires:
                            user = User(payload['sub'], payload['email'])
                        else:
                            raise Exception("Token expired")
                    except (IndexError, KeyError, jwt.exceptions.PyJWTError):
                        raise Exception("Invalid token")
            else:
                user = check_auth(config, auth.username, auth.password)
            if not user:
                return authenticate()
            if not check_role(config, user, self._role):
                return authenticate()
            kwargs['user'] = user
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
    config = setup_state.app.simdb_config
    db_type = config.get_option("database.type")

    if db_type == "postgres":
        host = config.get_option("database.host")
        port = config.get_option("database.port")
        api.db = Database(Database.DBMS.POSTGRESQL, scopefunc=_app_ctx_stack.__ident_func__, host=host, port=port)
    elif db_type == "sqlite":
        import appdirs
        db_dir = appdirs.user_data_dir('simdb')
        db_file = os.path.join(db_dir, "remote.db")
        file = Path(config.get_option("database.file", default=db_file))
        os.makedirs(file.parent, exist_ok=True)
        api.db = Database(Database.DBMS.SQLITE, scopefunc=_app_ctx_stack.__ident_func__, file=file)
    else:
        raise RuntimeError(f"Unknown database type in configuration: {db_type}.")


@api.teardown_request
def remove_db_session(_error):
    if api.db:
        api.db.remove()


@api.route("/")
@requires_auth()
def index(user: User=Optional[None]):
    return jsonify(
        {
            "api": "simdb",
            "version": current_app.simdb_config.api_version,
            "server_version": __version__,
            "endpoints": [
                request.url + "simulations",
                request.url + "files",
                request.url + "validation_schema"
            ]
        })


@api.route("/token", methods=["GET"])
@requires_auth()
def token(user: User=Optional[None]):
    auth = request.authorization
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30),
        'iat': datetime.datetime.utcnow(),
        'sub': auth.username,
        'email': user.email,
    }
    ret = {
        'status': 'success',
        'token': jwt.encode(payload, current_app.config.get("SECRET_KEY"), algorithm='HS256')
    }
    return jsonify(ret)


@api.route("/reset", methods=["POST"])
@requires_auth("admin")
def reset_db(user: User=Optional[None]):
    api.db.reset()
    cache.clear()
    return jsonify({})


def cache_key(*args, **kwargs):
    return request.url


@api.route("/simulations", methods=["GET"])
@requires_auth()
@cache.cached(key_prefix=cache_key)
def list_simulations(user: User=Optional[None]):
    limit = request.headers.get('result-limit', 0)
    names = []
    constraints = []
    if request.args:
        constraints: List[Tuple[str, str, QueryType]] = []
        for name in request.args:
            names.append(name)
            values = request.args.getlist(name)
            for value in values:
                constraint = parse_query_arg(value)
                if constraint[0]:
                    constraints.append((name,) + constraint)

    if constraints:
        data = api.db.query_meta_data(constraints, names)
    else:
        data = api.db.list_simulation_data(meta_keys=names, limit=limit)

    return jsonify(data)


@api.route("/files", methods=["GET"])
@requires_auth()
@cache.cached(key_prefix=cache_key)
def list_files(user: User=Optional[None]):
    files = api.db.list_files()
    return jsonify([file.data() for file in files])


@api.route("/file/<string:file_uuid>", methods=["GET"])
@requires_auth()
def get_file(file_uuid: str, user: User=Optional[None]):
    try:
        file = api.db.get_file(file_uuid)
        return jsonify(file.data(recurse=True))
    except DatabaseError as err:
        return error(str(err))


def _save_chunked_file(file: FileStorage, chunk_info: Dict, path: Path, compressed: bool=True):
    with open(path, "r+b" if path.exists() else "wb") as file_out:
        file_out.seek(chunk_info['chunk_size'] * chunk_info['chunk'])
        if compressed:
            with gzip.GzipFile(fileobj=file, mode="rb") as gz_file:
                file_out.write(gz_file.read())
        else:
            file_out.write(file.stream.read())


def _stage_file_from_chunks(files: Iterable[FileStorage], chunk_info: Dict, sim_uuid: uuid.UUID,
                            sim_files: List[File], common_root: Path) -> None:
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
        path = _secure_path(sim_file.uri.path, common_root, staging_dir)
        os.makedirs(path.parent, exist_ok=True)
        file_chunk_info = chunk_info.get(sim_file.uuid.hex, {'chunk_size': 0, 'chunk': 0, 'num_chunks': 1})
        _save_chunked_file(file, file_chunk_info, path)


def _set_alias(alias: str):
    character = None
    if alias.endswith('-'):
        character = '-'
    elif alias.endswith('#'):
        character = '#'

    if not character:
        return None, -1

    next_id = 1
    aliases = api.db.get_aliases(alias)
    for existing_alias in aliases:
        existing_id = int(existing_alias.split(character)[1])
        if next_id <= existing_id:
            next_id = existing_id + 1
    alias = '%s%d' % (alias, next_id)

    return alias, next_id


def _verify_file(sim_uuid: uuid.UUID, sim_file: File, common_root: Path):
    if current_app.simdb_config.get_option("development.disable_checksum", default=False):
        return
    staging_dir = Path(current_app.simdb_config.get_option("server.upload_folder")) / sim_uuid.hex
    if sim_file.type == DataObject.Type.FILE:
        path = _secure_path(sim_file.uri.path, common_root, staging_dir)
        if not path.exists():
            raise ValueError('file %s does not exist' % path)
        checksum = sha1_checksum(URI(scheme='file', path=path))
        if sim_file.checksum != checksum:
            raise ValueError("checksum failed for file %s" % repr(sim_file))
    elif sim_file.type == DataObject.Type.IMAS:
        from ..imas.checksum import checksum as imas_checksum
        config = current_app.simdb_config
        user_folder = current_app.simdb_config.get_option("server.user_upload_folder", default=None)
        uri = sim_file.uri
        if user_folder is not None:
            server_folder = current_app.simdb_config.get_option("server.upload_folder")
            uri.query['path'] = uri.query['path'].replace(str(user_folder), str(server_folder))
        checksum = imas_checksum(uri)
        if sim_file.checksum != checksum:
            raise ValueError("checksum failed for IDS %s" % uri)


@api.route("/files", methods=["POST"])
@requires_auth()
def upload_file(user: User=Optional[None]):
    try:
        data = request.get_json()
        if data:
            simulation = Simulation.from_data(data["simulation"])
            for file in data['files']:
                file_uuid = uuid.UUID(file['file_uuid'])
                file_type = file['file_type']
                sim_files = simulation.inputs if file_type == 'input' else simulation.outputs
                sim_file = next((f for f in sim_files if f.uuid == file_uuid), None)
                if sim_file is None:
                    raise ValueError("file with uuid %s not found in simulation" % file_uuid)
                common_root = os.path.commonpath([f.uri.path for f in chain(simulation.inputs, simulation.outputs)])
                _verify_file(simulation.uuid, sim_file, common_root)
            return jsonify({})

        from ..json import CustomDecoder
        data = json.load(request.files["data"], cls=CustomDecoder)

        if "simulation" not in data:
            return error("Simulation data not provided")

        simulation = Simulation.from_data(data["simulation"])

        chunk_info = data.get("chunk_info", {})
        file_type = data['file_type']

        files = request.files.getlist("files")
        if not files:
            return error("No files given")

        all_sim_files = list(chain(simulation.inputs, simulation.outputs))
        common_root = Path(os.path.commonpath([f.uri.path for f in all_sim_files]))

        sim_files = simulation.inputs if file_type == 'input' else simulation.outputs
        _stage_file_from_chunks(files, chunk_info, simulation.uuid, sim_files, common_root)

        return jsonify({})
    except ValueError as err:
        return error(str(err))


@api.route("/simulations", methods=["POST"])
@requires_auth()
def ingest_simulation(user: User=Optional[None]):
    try:
        data = request.get_json()

        if "simulation" not in data:
            return error("Simulation data not provided")

        simulation = Simulation.from_data(data["simulation"])
        simulation.user = user.name

        if "alias" in data["simulation"]:
            alias = data["simulation"]["alias"]
            (updated_alias, next_id) = _set_alias(alias)
            if updated_alias:
                simulation.meta.append(MetaData('seqid', next_id))
                simulation.alias = updated_alias
            else:
                simulation.alias = alias
        else:
            simulation.alias = simulation.uuid.hex[0:8]

        staging_dir = Path(current_app.simdb_config.get_option("server.upload_folder")) / simulation.uuid.hex

        files = list(chain(simulation.inputs, simulation.outputs))
        if files:
            common_root = os.path.commonpath([f.uri.path for f in files])
        else:
            common_root = ''

        for sim_file in files:
            path = _secure_path(sim_file.uri.path, common_root, staging_dir)
            if not path.exists():
                raise ValueError('simulation file %s not uploaded' % sim_file.uuid)
            if sim_file.uri.scheme.name == 'file':
                sim_file.uri = URI(scheme='file', path=path)

        result = {
            'ingested': simulation.uuid.hex,
        }

        if current_app.simdb_config.get_option("validation.auto_validate", default=False):
            result['validation'] = _validate(simulation)

        if current_app.simdb_config.get_option("validation.error_on_fail", default=False):
            if simulation.status == Simulation.Status.NOT_VALIDATED:
                raise Exception('Validation config option error_on_fail=True without auto_validate=True.')
            elif simulation.status == Simulation.Status.FAILED:
                result["error"] = 'Simulation validation failed and server has error_on_fail=True.'
                response = jsonify(result)
                response.status_code = 400
                return response

        replaces = simulation.find_meta("replaces")
        if not current_app.simdb_config.get_option("development.disable_replaces", default=False):
            if replaces and replaces[0].value:
                sim_id = replaces[0].value
                try:
                    replaces_sim = api.db.get_simulation(sim_id)
                except Exception:
                    replaces_sim = None
                if replaces_sim is None:
                    pass
                    # raise ValueError(f'Simulation replaces:{sim_id} is not a valid simulation identifier.')
                else:
                    _update_simulation_status(replaces_sim, Simulation.Status.DEPRECATED, user)
                    replaces_sim.set_meta('replaced_by', simulation.uuid)
                    api.db.insert_simulation(replaces_sim)

        api.db.insert_simulation(simulation)
        cache.clear()

        return jsonify(result)
    except (DatabaseError, ValueError) as err:
        return error(str(err))


def _validate(simulation, user) -> Dict:
    from ..validation import ValidationError, Validator
    schema = Validator.validation_schema()
    try:
        Validator(schema).validate(simulation)
        _update_simulation_status(simulation, Simulation.Status.PASSED, user)
        return {
            'passed': True,
        }
    except ValidationError as err:
        _update_simulation_status(simulation, Simulation.Status.FAILED, user)
        return {
            'passed': False,
            'error': str(err),
        }


@api.route("/validate/<string:sim_id>", methods=["POST"])
@requires_auth()
def validate(sim_id, user: User=Optional[None]):
    try:
        simulation = api.db.get_simulation(sim_id)
        result = _validate(simulation, user)
        api.db.insert_simulation(simulation)
        cache.clear()
        return jsonify(result)
    except DatabaseError as err:
        return error(str(err))


@api.route("/simulation/<path:sim_id>", methods=["GET"])
@requires_auth()
def get_simulation(sim_id: str, user: User=Optional[None]):
    try:
        simulation = api.db.get_simulation(sim_id)
        return jsonify(simulation.data(recurse=True))
    except DatabaseError as err:
        return error(str(err))


def _build_trace(sim_id: str) -> dict:
    try:
        simulation = api.db.get_simulation(sim_id)
    except DatabaseError as err:
        return {'error': str(err)}
    data = simulation.data(recurse=False)

    status = simulation.find_meta('status')
    if status:
        status = status[0].value
        if isinstance(status, str):
            data['status'] = status
        else:
            data['status'] = status.value
        status_on_name = data['status'] + '_on'
        status_on = simulation.find_meta(status_on_name)
        if status_on:
            data[status_on_name] = status_on[0].value

    replaces = simulation.find_meta("replaces")
    if replaces:
        data['replaces'] = _build_trace(replaces[0].value)

    replaced_on = simulation.find_meta('replaced_on')
    if replaced_on:
        data['deprecated_on'] = replaced_on[0].value

    replaces_reason = simulation.find_meta('replaces_reason')
    if replaces_reason:
        data['replaces_reason'] = replaces_reason[0].value

    return data


@api.route("/trace/<path:sim_id>", methods=["GET"])
@requires_auth()
def get_trace(sim_id: str, user: User=Optional[None]):
    try:
        data = _build_trace(sim_id)
        return jsonify(data)
    except DatabaseError as err:
        return error(str(err))


@api.route("/simulation/<path:sim_id>", methods=["PATCH"])
@requires_auth("admin")
def update_simulation(sim_id: str, user: User=Optional[None]):
    try:
        data = request.get_json()
        if "status" not in data:
            return error("Status not provided")
        simulation = api.db.get_simulation(sim_id)
        if simulation is None:
            raise ValueError(f"Simulation {sim_id} not found.")
        status = Simulation.Status(data["status"])
        _update_simulation_status(simulation, status, user)
        api.db.insert_simulation(simulation)
        cache.clear()
        return {}
    except DatabaseError as err:
        return error(str(err))


def _update_simulation_status(simulation: Simulation, status: Simulation.Status, user) -> None:
    from ..email.server import EmailServer

    old_status = simulation.status
    simulation.status = status
    simulation.set_meta(status.value.lower().replace(' ', '_') + '_on', datetime.datetime.now().isoformat())
    if status != old_status and simulation.watchers.count():
        server = EmailServer(current_app.simdb_config)
        msg = f"""\
Simulation status changed from {old_status} to {status}.

Updated by {user}.
"""
        to_addresses = [w.email for w in simulation.watchers]
        if to_addresses:
            server.send_message(f"Simulation {simulation.uuid.hex}", msg, to_addresses)


@api.route("/staging_dir/<string:sim_hex>", methods=["GET"])
@requires_auth()
def get_staging_dir(sim_hex: str, user: User=Optional[None]):
    upload_dir = current_app.simdb_config.get_option("server.user_upload_folder", default=None)
    user_folder = True
    if upload_dir is None:
        upload_dir = current_app.simdb_config.get_option("server.upload_folder")
        user_folder = False
    staging_dir = Path(current_app.simdb_config.get_option("server.upload_folder")) / sim_hex
    os.makedirs(staging_dir, exist_ok=True)
    # This needs to be done for ITER at the moment but should be removed once we can actually push IMAS data rather
    # than having to do a local copy onto the server directory.
    if user_folder:
        os.chmod(staging_dir, 0o777)
    return jsonify({'staging_dir': str(Path(upload_dir) / sim_hex)})


@api.route("/simulation/<path:sim_id>", methods=["DELETE"])
@requires_auth("admin")
def delete_simulation(sim_id: str, user: User=Optional[None]):
    try:
        simulation = api.db.delete_simulation(sim_id)
        cache.clear()
        files = []
        for file in itertools.chain(simulation.inputs, simulation.outputs):
            files.append("%s (%s)" % (file.uuid, file.file_name))
            os.remove(os.path.join(file.directory, file.file_name))
        if simulation.inputs or simulation.outputs:
            directory = simulation.inputs[0].directory if simulation.inputs else simulation.outputs[0].directory
            os.rmdir(directory)
        return jsonify({"deleted": {"simulation": simulation.uuid, "files": files}})
    except DatabaseError as err:
        return error(str(err))


@api.route("/watchers/<string:sim_id>", methods=["POST"])
@requires_auth()
def add_watcher(sim_id: str, user: User=Optional[None]):
    try:
        data = request.get_json()

        username = data["user"] if "user" in data else user.name
        email = data["email"] if "email" in data else user.email

        if "notification" not in data:
            return error("Watcher notification not provided")

        from ..notifications import Notification
        notification = getattr(Notification, data["notification"])

        watcher = Watcher(username, email, notification)
        api.db.add_watcher(sim_id, watcher)
        cache.clear()

        if username != user.name:
            # TODO: send email notify user that they have been added as a watcher
            pass

        return jsonify({"added": {"simulation": sim_id, "watcher": data["user"]}})
    except DatabaseError as err:
        return error(str(err))


@api.route("/watchers/<string:sim_id>", methods=["DELETE"])
@requires_auth()
def remove_watcher(sim_id: str, user: User=Optional[None]):
    try:
        data = request.get_json()

        username = data["user"] if "user" in data else user.name

        api.db.remove_watcher(sim_id, username)
        cache.clear()
        return jsonify({"removed": {"simulation": sim_id, "watcher": data["user"]}})
    except DatabaseError as err:
        return error(str(err))


@api.route("/watchers/<string:sim_id>", methods=["GET"])
@requires_auth()
def list_watchers(sim_id: str, user: User=Optional[None]):
    try:
        return jsonify([watcher.data(recurse=True) for watcher in api.db.list_watchers(sim_id)])
    except DatabaseError as err:
        return error(str(err))


@api.route("/validation_schema", methods=["GET"])
@requires_auth()
def get_validation_schema(user: User=Optional[None]):
    from ..validation.validator import Validator
    return jsonify(Validator.validation_schema())

