import datetime
from pathlib import Path

import appdirs
import jwt
from flask import Blueprint, Response, _app_ctx_stack, jsonify, request
from flask_restx import Resource

from simdb import __version__
from simdb.database import Database
from simdb.remote.core.auth import AuthenticationError, User, requires_auth
from simdb.remote.core.typing import current_app
from simdb.validation.validator import Validator

from .v1 import api as api_v1
from .v1 import namespaces as namespaces_v1
from .v1_1 import api as api_v1_1
from .v1_1 import namespaces as namespaces_v1_1
from .v1_2 import api as api_v1_2
from .v1_2 import namespaces as namespaces_v1_2


def error(message: str) -> Response:
    response = jsonify(error=message)
    response.status_code = 500
    return response


blueprints = {}


def register(api, version, namespaces):
    version_str = version.replace(".", "_")
    blueprint = Blueprint(f"api_{version_str}", f"{__name__}.{version_str}")
    blueprints[version] = blueprint
    api.init_app(blueprint)

    for namespace in namespaces:
        api.add_namespace(namespace)

    @blueprint.record
    def setup_db(setup_state):
        config = setup_state.app.simdb_config
        db_type = config.get_option("database.type")

        if db_type == "postgres":
            args = config.get_section("database")
            setup_state.app.db = Database(
                Database.DBMS.POSTGRESQL,
                scopefunc=_app_ctx_stack.__ident_func__,
                **args,
            )
        elif db_type == "sqlite":
            db_dir = appdirs.user_data_dir("simdb")
            file = Path(config.get_option("database.file", default=None)) or Path(
                db_dir, "remote.db"
            )
            file.parent.mkdir(parents=True)
            setup_state.app.db = Database(
                Database.DBMS.SQLITE, scopefunc=_app_ctx_stack.__ident_func__, file=file
            )
        else:
            raise RuntimeError(f"Unknown database type in configuration: {db_type}.")

    @blueprint.teardown_request
    def remove_db_session(_error):
        if current_app.db:
            current_app.db.remove()

    @api.errorhandler(AuthenticationError)
    def handle_authentication_error(err: Exception):
        return {"message": str(err)}, 401

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
                        request.url + "metadata",
                        request.url + "upload_options",
                    ],
                    "documentation": request.url + "docs",
                }
            )

    @api.route("/token")
    class Token(Resource):
        @api.doc(security="basicAuth")
        @api.response(200, "Success")
        @api.response(401, "Unauthorized")
        @requires_auth()
        def get(self, user: User):
            auth = request.authorization
            lifetime = current_app.simdb_config.get_option(
                "server.token_lifetime", default=30
            )
            payload = {
                "exp": datetime.datetime.utcnow() + datetime.timedelta(days=lifetime),
                "iat": datetime.datetime.utcnow(),
                "sub": auth.username,
                "email": user.email,
            }
            ret = {
                "status": "success",
                "token": jwt.encode(
                    payload, current_app.config.get("SECRET_KEY"), algorithm="HS256"
                ),
            }
            return jsonify(ret)

    @api.route("/validation_schema")
    class ValidationSchema(Resource):
        @requires_auth()
        def get(self, user: User):
            config = current_app.simdb_config
            return jsonify(Validator.validation_schemas(config, None))

    @api.route("/upload_options")
    class UploadOptions(Resource):
        @requires_auth()
        def get(self, user: User):
            config = current_app.simdb_config
            options = {
                "copy_files": config.get_option("server.copy_files", default=True),
                "copy_ids": config.get_option("server.copy_ids", default=True),
            }

            return jsonify(options)


register(api_v1, "v1", namespaces_v1)
register(api_v1_1, "v1.1", namespaces_v1_1)
register(api_v1_2, "v1.2", namespaces_v1_2)
