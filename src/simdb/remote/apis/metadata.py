from flask import current_app, jsonify
from flask_restx import Resource, Namespace

from ..core.errors import error
from ...database import DatabaseError
from ..core.cache import cache, cache_key

api = Namespace('metadata', path='/')


@api.route("/metadata")
class MetaData(Resource):

    @cache.cached(key_prefix=cache_key)
    def get(self):
        try:
            return jsonify(current_app.db.list_metadata_keys())
        except DatabaseError as err:
            return error(str(err))
