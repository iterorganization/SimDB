import logging
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_compress import Compress
from typing import Optional, cast, Type
from flask.json import JSONEncoder, JSONDecoder

from .apis import blueprints
from .core.cache import cache
from .core.typing import SimDBApp
from .core.auth import get_authenticator
from ..config import Config
from ..json import CustomEncoder, CustomDecoder

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
        authentication_type = config.get_option("authentication.type")
        authenticator = get_authenticator(authentication_type)
        return jsonify(
            {"endpoints": endpoints, "authentication": type(authenticator).Name}
        )

    for version, blueprint in blueprints.items():
        app.register_blueprint(blueprint, url_prefix=f"/{version}")

    return app
