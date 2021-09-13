from flask import current_app, jsonify
from flask_restx import Resource, Namespace

from simdb.remote.core.errors import error
from simdb.database import DatabaseError
from simdb.remote.core.cache import cache, cache_key

api = Namespace('metadata', path='/')


@api.route("/metadata")
class MetaData(Resource):

    @cache.cached(key_prefix=cache_key)
    def get(self):
        try:
            return jsonify(current_app.db.list_metadata_keys())
        except DatabaseError as err:
            return error(str(err))
