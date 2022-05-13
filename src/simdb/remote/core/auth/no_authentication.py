from typing import Optional

from ....config import Config
from ._authenticator import Authenticator
from ._user import User


class NoopAuthenticator(Authenticator):
    """
    No-op authenticator which accepts any user as authenticated.
    """

    Name = "None"

    def authenticate(self, username: str, _password: str, _config: Config) -> Optional[User]:
        return User(username, "")

