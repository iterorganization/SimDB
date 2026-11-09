from typing import Annotated

from flask_restx import Namespace, Resource

from simdb.database import DatabaseError, models
from simdb.notifications import Notification
from simdb.remote.core.auth import User, requires_auth
from simdb.remote.core.cache import clear_cache
from simdb.remote.core.pydantic_utils import (
    Body,
    ResponseException,
    pydantic_validate,
)
from simdb.remote.core.typing import current_app
from simdb.remote.models import (
    WatcherDeleteRequest,
    WatcherDeleteResponse,
    WatcherGetResponse,
    WatcherPostRequest,
    WatcherPostResponse,
)

api = Namespace("watchers", path="/")


@api.route("/watchers/<path:sim_id>")
class Watcher(Resource):
    @requires_auth()
    @pydantic_validate(api)
    def post(
        self, sim_id: str, user: User, data: Annotated[WatcherPostRequest, Body()]
    ) -> WatcherPostResponse:
        """Add a watcher to a simulation.

        Registers a user to be notified (by email) about changes to the
        simulation identified by ``sim_id``. The watcher's username, email and
        notification level default to those of the authenticated user when not
        supplied in the request body.
        """
        username = data.user or user.name
        email = data.email or user.email

        notification = getattr(Notification, data.notification)

        watcher = models.Watcher(username, email, notification)
        try:
            simulation = current_app.db.add_watcher(sim_id, watcher)
        except DatabaseError as err:
            raise ResponseException(str(err), 404) from err
        clear_cache()

        if username != user.name:
            # TODO: send email to notify user that they have been added as a watcher
            pass

        return WatcherPostResponse.model_validate(
            {"added": {"simulation": simulation.uuid, "watcher": username}}
        )

    @requires_auth()
    @pydantic_validate(api)
    def delete(
        self, sim_id: str, user: User, data: Annotated[WatcherDeleteRequest, Body()]
    ) -> WatcherDeleteResponse:
        """Remove a watcher from a simulation.

        Stops notifying the given user about changes to the simulation
        identified by ``sim_id``. The username defaults to the authenticated
        user when not supplied in the request body.
        """
        username = data.user or user.name

        try:
            simulation = current_app.db.remove_watcher(sim_id, username)
        except DatabaseError as err:
            raise ResponseException(str(err), 404) from err
        clear_cache()
        return WatcherDeleteResponse.model_validate(
            {"removed": {"simulation": simulation.uuid, "watcher": username}}
        )

    @requires_auth()
    @pydantic_validate(api)
    def get(self, sim_id: str, user: User) -> WatcherGetResponse:
        """List the watchers of a simulation.

        Returns every user currently watching the simulation identified by
        ``sim_id``, along with their notification settings.
        """
        try:
            watchers = current_app.db.list_watchers(sim_id)
        except DatabaseError as err:
            raise ResponseException(str(err), 404) from err
        return WatcherGetResponse([watcher.to_model() for watcher in watchers])
