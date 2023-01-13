from flask import request, current_app, jsonify, Blueprint, _app_ctx_stack, Response
from flask_restx import Resource
from pathlib import Path
import datetime
import jwt
import os

from ... import __version__
from ..core.auth import User, requires_auth, AuthenticationError
from ...database import Database
from .v1 import api as api_v1, namespaces as namespaces_v1
from .v1_1 import api as api_v1_1, namespaces as namespaces_v1_1
from .v1_2 import api as api_v1_2, namespaces as namespaces_v1_2


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
            import appdirs

            db_dir = appdirs.user_data_dir("simdb")
            db_file = os.path.join(db_dir, "remote.db")
            file = Path(config.get_option("database.file", default=db_file))
            os.makedirs(file.parent, exist_ok=True)
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
            from ...validation.validator import Validator

            config = current_app.simdb_config
            return jsonify(Validator.validation_schemas(config, None))


register(api_v1, "v1", namespaces_v1)
register(api_v1_1, "v1.1", namespaces_v1_1)
register(api_v1_2, "v1.2", namespaces_v1_2)
