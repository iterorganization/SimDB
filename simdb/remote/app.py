from flask import Flask, jsonify, request
import ssl
import os
import appdirs

from .api import api
from .. import __version__

dir_path = appdirs.user_config_dir('simdb')

app = Flask(__name__)
app.config.from_pyfile(os.path.join(dir_path, "app.cfg"))

@app.route("/")
def index():
    return jsonify({"urls": [ request.url + "api/v" + __version__  ]})

app.register_blueprint(api, url_prefix="/api/v" + __version__)

def run():
    if app.config['SSL_ENABLED']:
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(os.path.join(dir_path, "server.crt"), keyfile=os.path.join(dir_path, "server.key"))
        app.run(host='0.0.0.0', port='5000', ssl_context=context)
    else:
        app.run(host='0.0.0.0', port='5000')
