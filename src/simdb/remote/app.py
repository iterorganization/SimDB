import logging
import os
from typing import Optional, Type, cast

from flask import Flask, jsonify, request
from flask.json import JSONDecoder, JSONEncoder
from flask_compress import Compress
from flask_cors import CORS

from simdb.config import Config
from simdb.json import CustomDecoder, CustomEncoder

from .apis import blueprints
from .core.auth._authenticator import Authenticator
from .core.cache import cache
from .core.typing import SimDBApp

compress = Compress()


def create_app(
    config: Optional[Config] = None, testing=False, debug=False, profile=False
):
    if config is None:
        config_file = os.environ.get("SIMDB_CONFIG_FILE", default="app.cfg")
        config = Config(config_file)
        config.load()
    flask_options = {k.upper(): v for (k, v) in config.get_section("flask", {}).items()}

    app = cast(SimDBApp, Flask(__name__))
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.config["TESTING"] = testing
    app.config["DEBUG"] = debug
    app.config["PROFILE"] = profile
    app.json_encoder = cast(Type[JSONEncoder], CustomEncoder)
    app.json_decoder = cast(Type[JSONDecoder], CustomDecoder)
    app.config.from_mapping(flask_options)
    app.simdb_config = config
    cache.init_app(app)
    compress.init_app(app)

    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers.extend(gunicorn_logger.handlers)
    app.logger.setLevel(gunicorn_logger.level)

    @app.route("/")
    def index():
        endpoints = []
        for ver in blueprints:
            endpoints.append(f"{request.url}{ver}")
        authentication_types = config.get_string_option("authentication.type").split(
            ","
        )
        authenticators = [
            Authenticator.get(auth_type) for auth_type in authentication_types
        ]
        return jsonify(
            {
                "endpoints": endpoints,
                "authentication": authenticators[0].Name,
                "authenticators": [auth.Name for auth in authenticators],
            }
        )

    for version, blueprint in blueprints.items():
        app.register_blueprint(blueprint, url_prefix=f"/{version}")

    return app
