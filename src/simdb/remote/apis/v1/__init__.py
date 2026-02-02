from pathlib import Path

from flask import jsonify
from flask_restx import Api, Resource

from simdb.remote.apis.files import api as file_ns
from simdb.remote.apis.metadata import api as metadata_ns
from simdb.remote.apis.watchers import api as watcher_ns
from simdb.remote.core.auth import TokenAuthenticator, User, requires_auth
from simdb.remote.core.typing import current_app

from .simulations import api as sim_ns

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
            "name": TokenAuthenticator.TOKEN_HEADER_NAME,
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
        staging_dir.mkdir(parents=True, exist_ok=True)
        # This needs to be done for ITER at the moment but should be removed once we can actually push IMAS data
        # rather than having to do a local copy onto the server directory.
        if user_folder:
            staging_dir.chmod(0o777)
        return jsonify({"staging_dir": str(Path(upload_dir) / sim_hex)})
