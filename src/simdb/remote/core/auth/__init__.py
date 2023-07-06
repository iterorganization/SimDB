from flask import Response, request
from typing import Optional
from functools import wraps
import datetime
import jwt

from ._user import User
from ._exceptions import AuthenticationError

from .active_directory import ActiveDirectoryAuthenticator
from .ldap import LdapAuthenticator
from .no_authentication import NoopAuthenticator
from ..errors import error
from ..typing import current_app
from ....config import Config

__all__ = [
    User,
    AuthenticationError,
    ActiveDirectoryAuthenticator,
    LdapAuthenticator,
    NoopAuthenticator,
]

TOKEN_HEADER_NAME: str = "Authorization"

Authenticators = {
    ActiveDirectoryAuthenticator.Name.lower(): ActiveDirectoryAuthenticator,
    LdapAuthenticator.Name.lower(): LdapAuthenticator,
    NoopAuthenticator.Name.lower(): NoopAuthenticator,
}


def get_authenticator(name: str):
    """
    Find an authenticator class for the given name and return an object of that class.

    :param name: The name of the authenticator to return.
    :return: An instance of an Authenticator subclass.
    """
    try:
        return object.__new__(Authenticators[name.lower()])
    except KeyError:
        raise AuthenticationError(
            f"Unknown authenticator {name} selected in configuration"
        )


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


def check_auth(config, username, password) -> Optional[User]:
    """
    This function is called to check if a username / password combination is valid.
    """
    if username == "admin" and password == config.get_option("server.admin_password"):
        return User("admin", None)

    authentication_type = config.get_option("authentication.type")
    authenticator = get_authenticator(authentication_type)
    return authenticator.authenticate(username, password, config)


class RequiresAuth:
    def __init__(self, role=None):
        self._role = role

    def __call__(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            config = current_app.simdb_config
            auth = request.authorization
            user: Optional[User] = None
            if not auth:
                if request.headers.get(TOKEN_HEADER_NAME, ""):
                    try:
                        (name, token) = request.headers[TOKEN_HEADER_NAME].split(
                            " "
                        )
                        if name != "JWT-Token":
                            raise AuthenticationError("Invalid token")
                        payload = jwt.decode(
                            token.strip(),
                            current_app.config.get("SECRET_KEY"),
                            algorithms=["HS256"],
                        )
                        expires = datetime.datetime.fromtimestamp(payload["exp"])
                        if datetime.datetime.utcnow() < expires:
                            user = User(payload["sub"], payload["email"])
                        else:
                            raise AuthenticationError("Token expired")
                    except (IndexError, KeyError, jwt.exceptions.PyJWTError) as ex:
                        raise AuthenticationError(f"Invalid token: {ex}")
                elif config.get_option("authentication.firewall_auth", default=False):
                    firewall_header = config.get_option(
                        "authentication.firewall_header", default=None
                    )
                    if not firewall_header:
                        return error(
                            "Firewall auth enabled but no firewall header name defined"
                        )
                    try:
                        user = User(request.headers[firewall_header], "")
                    except KeyError:
                        raise AuthenticationError(f"Header {firewall_header} not found")
            else:
                user = check_auth(config, auth.username, auth.password)
            if not user:
                return authenticate()
            if not check_role(config, user, self._role):
                return authenticate()
            kwargs["user"] = user
            return f(*args, **kwargs)

        return decorated


def requires_auth(*args):
    return RequiresAuth(*args)
