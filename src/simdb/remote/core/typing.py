from flask import Flask
from flask import current_app as _current_app
from typing import cast, Type

from ...config import Config
from ...database import Database


class SimDBApp(Flask):
    """
    Wrapper class for typing of SimDB Flask app with additional fields to hold configuration and database.
    """

    simdb_config: Config
    db: Database


current_app = cast(SimDBApp, _current_app)
