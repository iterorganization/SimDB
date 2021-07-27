from flask import request, current_app, jsonify, Response
from flask_restx import Resource, Namespace

from ..core.auth import User, requires_auth
from ..core.cache import cache
from ...database import DatabaseError


api = Namespace('watchers', path='/')


def error(message: str) -> Response:
    response = jsonify(error=message)
    response.status_code = 500
    return response


@api.route("/watchers/<string:sim_id>")
class Watcher(Resource):

    @requires_auth()
    def post(self, sim_id: str, user: User):
        try:
            data = request.get_json()

            username = data["user"] if "user" in data else user.name
            email = data["email"] if "email" in data else user.email

            if "notification" not in data:
                return error("Watcher notification not provided")

            from ...notifications import Notification
            notification = getattr(Notification, data["notification"])

            watcher = Watcher(username, email, notification)
            current_app.db.add_watcher(sim_id, watcher)
            cache.clear()

            if username != user.name:
                # TODO: send email to notify user that they have been added as a watcher
                pass

            return jsonify({"added": {"simulation": sim_id, "watcher": data["user"]}})
        except DatabaseError as err:
            return error(str(err))

    @requires_auth()
    def delete(self, sim_id: str, user: User):
        try:
            data = request.get_json()

            username = data["user"] if "user" in data else user.name

            current_app.db.remove_watcher(sim_id, username)
            cache.clear()
            return jsonify({"removed": {"simulation": sim_id, "watcher": data["user"]}})
        except DatabaseError as err:
            return error(str(err))

    @requires_auth()
    def get(self, sim_id: str, user: User):
        try:
            return jsonify([watcher.data(recurse=True) for watcher in current_app.db.list_watchers(sim_id)])
        except DatabaseError as err:
            return error(str(err))
