from flask import jsonify
from flask_restx import Namespace, Resource

from ...database import DatabaseError
from ...remote.core.cache import cache, cache_key
from ...remote.core.errors import error
from ..core.typing import current_app

api = Namespace("metadata", path="/")


@api.route("/metadata")
class MetaData(Resource):
    @cache.cached(key_prefix=cache_key)
    def get(self):
        try:
            return jsonify(current_app.db.list_metadata_keys())
        except DatabaseError as err:
            return error(str(err))


@api.route("/metadata/<string:name>")
class MetaDataValues(Resource):
    @cache.cached(key_prefix=cache_key)
    def get(self, name):
        try:
            return jsonify(current_app.db.list_metadata_values(name))
        except DatabaseError as err:
            return error(str(err))
