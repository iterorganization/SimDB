import abc
from typing import Optional

from ....config import Config
from ._user import User


class Authenticator(abc.ABC):
    """
    Base class for SimDB server authenticators.
    """

    Name = NotImplemented

    @abc.abstractmethod
    def authenticate(
        self, username: str, password: str, config: Config
    ) -> Optional[User]:
        """
        Authenticate the user using the given username and password.

        Additional authentication options can be defined in the configuration specific to the type of authentication
        being performed - i.e. connection URI for LDAP server.

        :param username: The username provided by the user.
        :param password: The password provided by the user.
        :param config: The SimDB configuration object.
        :return: A User object if the user successfully authenticates, otherwise None.
        """
        ...
