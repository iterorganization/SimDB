from flask import current_app, jsonify
from flask_restx import Resource, Namespace

from ..core.errors import error
from ...database import DatabaseError


api = Namespace('metadata', path='/')


@api.route("/metadata")
class MetaData(Resource):

    def get(self):
        try:
            return jsonify(current_app.db.list_metadata_keys())
        except DatabaseError as err:
            return error(str(err))
