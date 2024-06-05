from typing import Optional
from flask import Request

from ....config import Config
from ..typing import current_app
from ._authenticator import Authenticator
from ._user import User
from ._exceptions import AuthenticationError


class TokenAuthenticator(Authenticator):

    TOKEN_HEADER_NAME: str = "Authorization"

    Name = "Token"

    def authenticate(
        self, config: Config, request: Request
    ) -> Optional[User]:
        import jwt
        import datetime

        try:
            token = request.headers.get(TokenAuthenticator.TOKEN_HEADER_NAME, "")

            (name, token) = token

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
