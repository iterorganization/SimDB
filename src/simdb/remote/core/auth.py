from flask import Response, current_app, request
from typing import Optional
from collections import namedtuple
from functools import wraps
import datetime
import jwt


User = namedtuple("User", ("name", "email"))


HEADER_NAME = 'Authorization'


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response("Could not verify your access level for that URL. You have to login with proper credentials",
                    401, {"WWW-Authenticate": "Basic realm='Login Required'"})


def check_role(config, user: User, role: Optional[str]) -> bool:
    config = current_app.simdb_config

    if role:
        import csv

        users = config.get_option(f'role.{role}.users', default='')
        reader = csv.reader([users])
        for row in reader:
            if user.name in row:
                return True
        return False

    return True


def check_auth(config, username, password) -> Optional[User]:
    """This function is called to check if a username / password combination is valid.
    """
    from easyad import EasyAD

    if username == "admin" and password == config.get_option("server.admin_password"):
        return User("admin", None)

    try:
        ad_config = {
            'AD_SERVER': config.get_option('server.ad_server'),
            'AD_DOMAIN': config.get_option('server.ad_domain'),
        }
        ad = EasyAD(ad_config)
    except KeyError:
        return None

    user = ad.authenticate_user(username, password, json_safe=True)
    if user:
        return User(user["sAMAccountName"], user["mail"])
    else:
        return None


class AuthenticationError(Exception):
    pass


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
                if request.headers.get(HEADER_NAME, ''):
                    try:
                        (name, token) = request.headers[HEADER_NAME].split(' ')
                        if name != 'JWT-Token':
                            raise AuthenticationError("Invalid token")
                        payload = jwt.decode(token.strip(), current_app.config.get('SECRET_KEY'), algorithms=['HS256'])
                        expires = datetime.datetime.fromtimestamp(payload['exp'])
                        if datetime.datetime.utcnow() < expires:
                            user = User(payload['sub'], payload['email'])
                        else:
                            raise AuthenticationError("Token expired")
                    except (IndexError, KeyError, jwt.exceptions.PyJWTError) as ex:
                        raise AuthenticationError(f"Invalid token: {ex}")
            else:
                user = check_auth(config, auth.username, auth.password)
            if not user:
                return authenticate()
            if not check_role(config, user, self._role):
                return authenticate()
            kwargs['user'] = user
            return f(*args, **kwargs)
        return decorated


def requires_auth(*args):
    return RequiresAuth(*args)
