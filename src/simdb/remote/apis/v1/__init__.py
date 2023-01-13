import os
from pathlib import Path
from flask_restx import Api, Resource
from flask import jsonify, current_app

from ...core.auth import HEADER_NAME, requires_auth, User
from .simulations import api as sim_ns
from ..files import api as file_ns
from ..metadata import api as metadata_ns
from ..watchers import api as watcher_ns

api = Api(
    title="SimDB REST API",
    version="1.0",
    description="SimDB REST API",
    authorizations={
        "basicAuth": {
            "type": "basic",
        },
        "apiToken": {
            "type": "apiKey",
            "in": "header",
            "name": HEADER_NAME,
        },
    },
    security=["basicAuth", "apiToken"],
    doc="/docs",
)

api.add_namespace(sim_ns)
namespaces = [metadata_ns, watcher_ns, file_ns, sim_ns]


@api.route("/staging_dir/<string:sim_hex>")
class StagingDirectory(Resource):
    @requires_auth()
    def get(self, sim_hex: str, user: User):
        upload_dir = current_app.simdb_config.get_option(
            "server.user_upload_folder", default=None
        )
        user_folder = True
        if upload_dir is None:
            upload_dir = current_app.simdb_config.get_option("server.upload_folder")
            user_folder = False

        staging_dir = (
            Path(current_app.simdb_config.get_option("server.upload_folder")) / sim_hex
        )
        os.makedirs(staging_dir, exist_ok=True)
        # This needs to be done for ITER at the moment but should be removed once we can actually push IMAS data
        # rather than having to do a local copy onto the server directory.
        if user_folder:
            os.chmod(staging_dir, 0o777)
        return jsonify({"staging_dir": str(Path(upload_dir) / sim_hex)})
