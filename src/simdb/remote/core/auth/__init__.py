from flask import Response, request, Request
from typing import Optional
from functools import wraps

from ._user import User
from ._exceptions import AuthenticationError
from ._authenticator import Authenticator

from .active_directory import ActiveDirectoryAuthenticator
from .firewall import FirewallAuthenticator
from .keycloak import KeyCloakAuthenticator
from .ldap import LdapAuthenticator
from .no_authentication import NoopAuthenticator
from .token import TokenAuthenticator
from ..typing import current_app
from ....config import Config

__all__ = [
    User,
    AuthenticationError,
    ActiveDirectoryAuthenticator,
    FirewallAuthenticator,
    KeyCloakAuthenticator,
    LdapAuthenticator,
    NoopAuthenticator,
    TokenAuthenticator,
]

Authenticator.register(ActiveDirectoryAuthenticator)
Authenticator.register(FirewallAuthenticator)
Authenticator.register(KeyCloakAuthenticator)
Authenticator.register(LdapAuthenticator)
Authenticator.register(NoopAuthenticator)
Authenticator.register(TokenAuthenticator)


def authenticate():
    """
    Sends a 401 response that enables basic auth.
    """
    return Response(
        "Could not verify your access level for that URL. You have to login with proper credentials.",
        401,
        {"WWW-Authenticate": "Basic realm='Login Required'"},
    )


def check_role(config: Config, user: User, role: Optional[str]) -> bool:
    """
    This function is called to check if an authenticated user is a member of the specified role.

    If no role is specified then the function always returns true.
    """
    if role:
        import csv

        users = config.get_option(f"role.{role}.users", default="")
        reader = csv.reader([users])
        for row in reader:
            if user.name in row:
                return True
        return False

    return True


def check_auth(
    config: Config, request: Request
) -> Optional[User]:
    """
    This function is called to check if a request is authenticated.
    """
    auth = request.authorization
    username = auth.username if auth is not None else None
    password = auth.password if auth is not None else None

    if username == "admin" and password == config.get_option("server.admin_password"):
        return User("admin", None)

    authentication_types = config.get_option("authentication.type").split(",")
    authentication_types = ['token'] + authentication_types
    for authentication_type in authentication_types:
        authenticator = Authenticator.get(authentication_type)
        user = authenticator.authenticate(config, request)
        if user is not None:
            return user

    return None


class RequiresAuth:
    def __init__(self, role=None):
        self._role = role

    def __call__(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            config = current_app.simdb_config
            user: Optional[User] = check_auth(config, request)

            if not user:
                return authenticate()

            if not check_role(config, user, self._role):
                return authenticate()

            kwargs["user"] = user
            return f(*args, **kwargs)

        return decorated


def requires_auth(*args):
    return RequiresAuth(*args)
