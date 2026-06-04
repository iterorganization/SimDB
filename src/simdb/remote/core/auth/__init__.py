import csv
from functools import wraps
from typing import Optional

from flask import Request, Response, request

from simdb.config import Config
from simdb.remote.core.typing import current_app

from ._authenticator import Authenticator
from ._exceptions import AuthenticationError
from ._user import User
from .firewall import FirewallAuthenticator
from .no_authentication import NoopAuthenticator
from .token import TokenAuthenticator

Authenticator.register(FirewallAuthenticator)
Authenticator.register(NoopAuthenticator)
Authenticator.register(TokenAuthenticator)

try:
    from .active_directory import ActiveDirectoryAuthenticator

    Authenticator.register(ActiveDirectoryAuthenticator)
except (ImportError, ModuleNotFoundError):
    pass

try:
    from .keycloak import KeyCloakAuthenticator

    Authenticator.register(KeyCloakAuthenticator)
except (ImportError, ModuleNotFoundError):
    pass
try:
    from .ldap import LdapAuthenticator

    Authenticator.register(LdapAuthenticator)
except (ImportError, ModuleNotFoundError):
    pass


__all__ = [
    "ActiveDirectoryAuthenticator",
    "AuthenticationError",
    "FirewallAuthenticator",
    "KeyCloakAuthenticator",
    "LdapAuthenticator",
    "NoopAuthenticator",
    "TokenAuthenticator",
    "User",
]


def authenticate():
    """
    Sends a 401 response that enables basic auth.
    """
    return Response(
        "Could not verify your access level for that URL. You have to login with "
        "proper credentials.",
        401,
        {"WWW-Authenticate": "Basic realm='Login Required'"},
    )


def check_role(config: Config, user: User, role: Optional[str]) -> bool:
    """
    This function is called to check if an authenticated user is a member of the
    specified role.

    If no role is specified then the function always returns true.
    """
    if role:
        users = config.get_string_option(f"role.{role}.users", default="")
        reader = csv.reader([users])
        return any(user.name in row for row in reader)

    return True


def check_auth(config: Config, request: Request) -> Optional[User]:
    """
    This function is called to check if a request is authenticated.
    """
    auth = request.authorization
    username = auth.username if auth is not None else None
    password = auth.password if auth is not None else None
    if username == "admin":
        if password == config.get_option("server.admin_password"):
            return User("admin", None)
        else:
            raise AuthenticationError(f"Authentication failed for user {username}")

    authentication_types = (
        config.get_string_option("authentication.type").lower().split(",")
    )
    if "token" not in authentication_types:
        authentication_types = ["token", *authentication_types]

    for authentication_type in authentication_types:
        authenticator = Authenticator.get(authentication_type)
        try:
            user = authenticator.authenticate(config, request)
            if user is not None:
                return user
        except AuthenticationError:
            AuthenticationError(
                f"Authentication failed for user {username} using "
                f"{authentication_type} authenticator."
            )
            ...

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
