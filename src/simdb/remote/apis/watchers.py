from flask import request, current_app, jsonify
from flask_restx import Resource, Namespace

from ..core.auth import User, requires_auth
from ..core.errors import error
from ..core.cache import clear_cache
from ...database import DatabaseError, models


api = Namespace("watchers", path="/")


@api.route("/watchers/<path:sim_id>")
class Watcher(Resource):
    @requires_auth()
    def post(self, sim_id: str, user: User):
        try:
            data = request.get_json()
            if data is None:
                return error("No data provided")

            username = data["user"] if "user" in data else user.name
            email = data["email"] if "email" in data else user.email

            if "notification" not in data:
                return error("Watcher notification not provided")

            from ...notifications import Notification

            notification = getattr(Notification, data["notification"])

            watcher = models.Watcher(username, email, notification)
            current_app.db.add_watcher(sim_id, watcher)
            clear_cache()

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
            clear_cache()
            return jsonify({"removed": {"simulation": sim_id, "watcher": data["user"]}})
        except DatabaseError as err:
            return error(str(err))

    @requires_auth()
    def get(self, sim_id: str, user: User):
        try:
            return jsonify(
                [
                    watcher.data(recurse=True)
                    for watcher in current_app.db.list_watchers(sim_id)
                ]
            )
        except DatabaseError as err:
            return error(str(err))
