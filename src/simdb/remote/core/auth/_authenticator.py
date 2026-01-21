import abc
from typing import Dict, Optional, Type

from flask import Request

from simdb.config import Config

from ._exceptions import AuthenticationError
from ._user import User


class Authenticator(abc.ABC):
    """
    Base class for SimDB server authenticators.
    """

    Authenticators: Dict[str, Type["Authenticator"]] = {}
    Name: str = NotImplemented

    @abc.abstractmethod
    def authenticate(
        self,
        config: Config,
        request: Request,
    ) -> Optional[User]:
        """
        Authenticate the user using parameters passed in the current request - i.e. username/password passed as part of
        SimpleAuth or a token in the request header.

        Additional authentication options can be defined in the configuration specific to the type of authentication
        being performed - i.e. connection URI for LDAP server.

        :param config: The SimDB configuration object.
        :param request: The Flask request object.
        :return: A User object if the user successfully authenticates, otherwise None.
        """
        ...

    @classmethod
    def get(cls, name: str) -> "Authenticator":
        """
        Find an authenticator subclass for the given name and return an object of that class.

        :param name: The name of the authenticator to return.
        :return: An instance of an Authenticator subclass.
        """
        try:
            return Authenticator.__new__(cls.Authenticators[name.lower()])
        except KeyError:
            raise AuthenticationError(
                f"Unknown authenticator {name} selected in configuration"
            )

    @classmethod
    def register(cls, authenticator: Type["Authenticator"]) -> None:
        cls.Authenticators[authenticator.Name.lower()] = authenticator
