from flask import Flask

from .api import api
from .. import __version__


app = Flask(__name__)
app.config.from_pyfile("/Users/jhollocombe/Projects/simdb/simdb/remote/app.cfg")


# @api.record
# def record_params(setup_state):
#     print(setup_state.app.config)
#     api.db_host = setup_state.app.config["DB_HOST"]
#     api.db_port = setup_state.app.config["DB_PORT"]


app.register_blueprint(api, url_prefix="/api/v" + __version__)
