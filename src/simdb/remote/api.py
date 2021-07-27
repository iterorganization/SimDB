from flask import request, current_app, jsonify, Blueprint, _app_ctx_stack, Response, g
from flask_restx import Api, Resource
from pathlib import Path
import datetime
import jwt
import os

from .. import __version__
from .core.auth import User, requires_auth, HEADER_NAME
from ..database import Database
from .apis import sim_ns, file_ns, watcher_ns


API_VERSION = 1

api = Api(
    title='SimDB REST API',
    version='1.0',
    description='SimDB REST API',
    authorizations={
        'basicAuth': {
            'type': 'basic',
        },
        'apiToken': {
            'type': 'apiKey',
            'in': 'header',
            'name': HEADER_NAME,
        }
    },
    security=['basicAuth', 'apiToken'],
    doc='/docs'
)


blueprint = Blueprint('api', __name__)
api.init_app(blueprint)
api.add_namespace(sim_ns)
api.add_namespace(file_ns)
api.add_namespace(watcher_ns)


def error(message: str) -> Response:
    response = jsonify(error=message)
    response.status_code = 500
    return response


@blueprint.record
def setup_db(setup_state):
    config = setup_state.app.simdb_config
    db_type = config.get_option("database.type")

    if db_type == "postgres":
        host = config.get_option("database.host")
        port = config.get_option("database.port")
        setup_state.app.db = Database(Database.DBMS.POSTGRESQL, scopefunc=_app_ctx_stack.__ident_func__, host=host, port=port)
    elif db_type == "sqlite":
        import appdirs
        db_dir = appdirs.user_data_dir('simdb')
        db_file = os.path.join(db_dir, "remote.db")
        file = Path(config.get_option("database.file", default=db_file))
        os.makedirs(file.parent, exist_ok=True)
        setup_state.app.db = Database(Database.DBMS.SQLITE, scopefunc=_app_ctx_stack.__ident_func__, file=file)
    else:
        raise RuntimeError(f"Unknown database type in configuration: {db_type}.")


@blueprint.teardown_request
def remove_db_session(_error):
    if current_app.db:
        current_app.db.remove()


@api.route("/")
class Index(Resource):

    @api.doc(security=[])
    def get(self):
        return jsonify(
            {
                "api": "simdb",
                "api_version": api.version,
                "server_version": __version__,
                "endpoints": [
                    request.url + "simulations",
                    request.url + "files",
                    request.url + "validation_schema",
                ],
                "documentation": request.url + "docs",
            })


@api.route("/token")
class Token(Resource):

    @api.doc(security='basicAuth')
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized')
    @requires_auth()
    def get(self, user: User):
        auth = request.authorization
        lifetime = current_app.simdb_config.get_option("server.token_lifetime", default=30)
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=lifetime),
            'iat': datetime.datetime.utcnow(),
            'sub': auth.username,
            'email': user.email,
        }
        ret = {
            'status': 'success',
            'token': jwt.encode(payload, current_app.config.get("SECRET_KEY"), algorithm='HS256')
        }
        return jsonify(ret)


@api.route("/staging_dir/<string:sim_hex>")
class StagingDirectory(Resource):

    @requires_auth()
    def get(self, sim_hex: str, user: User):
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


@api.route("/validation_schema")
class ValidationSchema(Resource):

    @requires_auth()
    def get(self, user: User):
        from ..validation.validator import Validator
        return jsonify(Validator.validation_schema())
