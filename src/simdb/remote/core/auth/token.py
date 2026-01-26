from typing import Optional

from flask import Request

from simdb.config import Config
from simdb.remote.core.typing import current_app

from ._authenticator import Authenticator
from ._exceptions import AuthenticationError
from ._user import User


class TokenAuthenticator(Authenticator):
    TOKEN_HEADER_NAME: str = "Authorization"

    Name = "Token"

    def authenticate(self, config: Config, request: Request) -> Optional[User]:
        import datetime

        import jwt

        try:
            token = request.headers.get(TokenAuthenticator.TOKEN_HEADER_NAME, "")

            (name, token) = token.split() if token else (None, None)

            if name != "JWT-Token":
                raise AuthenticationError("Invalid token")

            payload = jwt.decode(
                token.strip(),
                current_app.config.get("SECRET_KEY"),
                algorithms=["HS256"],
            )

            expires = datetime.datetime.fromtimestamp(payload["exp"])
            if datetime.datetime.utcnow() < expires:
                return User(payload["sub"], payload["email"])
            else:
                raise AuthenticationError("Token expired")

        except (IndexError, KeyError, jwt.exceptions.PyJWTError) as ex:
            raise AuthenticationError(f"Invalid token: {ex}")
