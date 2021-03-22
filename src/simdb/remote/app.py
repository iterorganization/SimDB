from flask import Flask, jsonify, request
import ssl

from .api import api
from ..config import Config
from .. import __version__

config = Config('app.cfg')
config.load()
flask_options = [(k.upper(), v) for (k, v) in config.get_section('flask', [])]

app = Flask(__name__)
app.config.from_mapping(flask_options)
app.simdb_config = config


@app.route("/")
def index():
    return jsonify({"urls": [request.url + "api/v" + __version__]})


app.register_blueprint(api, url_prefix="/api/v" + __version__)


def run():
    if config.get_option("server.ssl_enabled") == "True":
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(certfile=config.get_option("server.ssl_cert_file"),
                                keyfile=config.get_option("server.ssl_key_file"))
        app.run(host='0.0.0.0', port='5000', ssl_context=context)
    else:
        app.run(host='0.0.0.0', port='5000')
