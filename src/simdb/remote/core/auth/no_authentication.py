from typing import Optional

from ....config import Config
from ._authenticator import Authenticator
from ._user import User


class NoopAuthenticator(Authenticator):
    """
    No-op authenticator which accepts any user as authenticated.
    """

    Name = "None"

    def authenticate(
        self, username: Optional[str], _password: Optional[str], _config: Config
    ) -> Optional[User]:
        if username is None:
            return User("anonymous", None)
        return User(username, None)
