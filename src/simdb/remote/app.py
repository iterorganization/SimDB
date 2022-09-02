import os
from flask import Flask, jsonify, request
from flask_cors import CORS

from .apis import blueprints
from .core.cache import cache
from ..config import Config
from ..json import CustomEncoder, CustomDecoder


def create_app(config: Config = None, testing=False, debug=False, profile=False):
    if config is None:
        config_file = os.environ.get("SIMDB_CONFIG_FILE", default="app.cfg")
        config = Config(config_file)
        config.load()
    flask_options = [(k.upper(), v) for (k, v) in config.get_section("flask", {}).items()]

    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.config["TESTING"] = testing
    app.config["DEBUG"] = debug
    app.config["PROFILE"] = profile
    app.json_encoder = CustomEncoder
    app.json_decoder = CustomDecoder
    app.config.from_mapping(flask_options)
    app.simdb_config = config
    cache.init_app(app)

    @app.route("/")
    def index():
        endpoints = []
        for ver in blueprints:
            endpoints.append(f"{request.url}{ver}")
        return jsonify({"endpoints": endpoints})

    for version, blueprint in blueprints.items():
        app.register_blueprint(blueprint, url_prefix=f"/{version}")

    return app
