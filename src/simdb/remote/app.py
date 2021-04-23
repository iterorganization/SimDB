from flask import Flask, jsonify, request
from typing import Dict, Any
import ssl
import numpy as np
import base64
import json

from .api import api
from ..config import Config

config = Config('app.cfg')
config.load()
flask_options = [(k.upper(), v) for (k, v) in config.get_section('flask', [])]


def numpy_hook(obj: Dict) -> Any:
    if 'type' in obj and obj['type'] == 'numpy.ndarray':
        bytes = base64.decodebytes(obj['bytes'].encode())
        return np.frombuffer(bytes, dtype=obj['dtype'])
    return obj


class NumpyDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        kwargs['object_hook'] = numpy_hook
        super().__init__(*args, **kwargs)


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            bytes = base64.b64encode(obj).decode()
            return {'type': 'numpy.ndarray', 'dtype': obj.dtype.name, 'bytes': bytes}
        return json.JSONEncoder.default(self, obj)


app = Flask(__name__)
app.json_encoder = NumpyEncoder
app.json_decoder = NumpyDecoder
app.config.from_mapping(flask_options)
app.simdb_config = config


@app.route("/")
def index():
    return jsonify({"endpoints": [request.url + f"api/v{config.api_version}"]})


app.register_blueprint(api, url_prefix=f"/api/v{config.api_version}")


def run():
    if config.get_option("server.ssl_enabled"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(certfile=config.get_option("server.ssl_cert_file"),
                                keyfile=config.get_option("server.ssl_key_file"))
        app.run(host='0.0.0.0', port='5000', ssl_context=context)
    else:
        app.run(host='0.0.0.0', port='5000')
