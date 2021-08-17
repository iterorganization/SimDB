from flask import Flask, jsonify, request
from flask_cors import CORS

from .api import blueprint, api
from .core.cache import cache
from ..config import Config
from ..json import CustomEncoder, CustomDecoder


def create_app(config: Config=None, testing=False, debug=False, profile=False):
    if config is None:
        config = Config('app.cfg')
        config.load()
    flask_options = [(k.upper(), v) for (k, v) in config.get_section('flask', [])]

    app = Flask(__name__)
    CORS(app, resources={r'/api/*': {'origins': '*'}})
    app.config['TESTING'] = testing
    app.config['DEBUG'] = debug
    app.config['PROFILE'] = profile
    app.json_encoder = CustomEncoder
    app.json_decoder = CustomDecoder
    app.config.from_mapping(flask_options)
    app.simdb_config = config
    cache.init_app(app)

    @app.route("/")
    def index():
        return jsonify({"endpoints": [request.url + f"api/v{api.version}"]})

    app.register_blueprint(blueprint, url_prefix=f"/api/v{api.version}")
    return app
