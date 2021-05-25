from flask import Flask, jsonify, request
import ssl

from .api import api
from .cache import cache
from ..config import Config
from ..json import CustomEncoder, CustomDecoder

config = Config('app.cfg')
config.load()
flask_options = [(k.upper(), v) for (k, v) in config.get_section('flask', [])]


app = Flask(__name__)
app.json_encoder = CustomEncoder
app.json_decoder = CustomDecoder
app.config.from_mapping(flask_options)
app.simdb_config = config
cache.init_app(app)


@app.route("/")
def index():
    return jsonify({"endpoints": [request.url + f"api/v{config.api_version}"]})


app.register_blueprint(api, url_prefix=f"/api/v{config.api_version}")


def run():
    # from werkzeug.middleware.profiler import ProfilerMiddleware
    # app.config['PROFILE'] = True
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[50], sort_by=("cumtime",))

    if config.get_option("server.ssl_enabled"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(certfile=config.get_option("server.ssl_cert_file"),
                                keyfile=config.get_option("server.ssl_key_file"))
        app.run(host='0.0.0.0', port='5000', ssl_context=context)
    else:
        app.run(host='0.0.0.0', port='5000')
