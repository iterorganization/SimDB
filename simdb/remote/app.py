from flask import Flask
import ssl
import os

from .api import api
from .. import __version__


def run():
    dir_path = os.path.dirname(os.path.realpath(__file__))

    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_cert_chain(os.path.join(dir_path, "server.crt"), keyfile=os.path.join(dir_path, "server.key"))

    app = Flask(__name__)
    app.config.from_pyfile(os.path.join(dir_path, "app.cfg"))

    app.register_blueprint(api, url_prefix="/api/v" + __version__)

    #app.run(host='0.0.0.0', port='5000', debug=False, ssl_context=context)
    app.run(host='0.0.0.0', port='5000', debug=False)
