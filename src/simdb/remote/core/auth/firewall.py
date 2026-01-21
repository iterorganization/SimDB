from typing import Optional

from flask import Request

from simdb.config import Config

from ._authenticator import Authenticator
from ._exceptions import AuthenticationError
from ._user import User


class FirewallAuthenticator(Authenticator):
    Name = "Firewall"

    def authenticate(self, config: Config, request: Request) -> Optional[User]:
        firewall_user = config.get_option("authentication.firewall_user", default=None)
        firewall_email = config.get_option(
            "authentication.firewall_email", default=None
        )

        if not firewall_user:
            raise AuthenticationError(
                "Firewall auth enabled but authentication.firewall_user not defined"
            )

        if not firewall_email:
            raise AuthenticationError(
                "Firewall auth enabled but authentication.firewall_email not defined"
            )

        if firewall_user not in request.headers:
            raise AuthenticationError(f"Header {firewall_user} not found")

        if firewall_email not in request.headers:
            raise AuthenticationError(f"Header {firewall_email} not found")

        return User(request.headers[firewall_user], request.headers[firewall_email])
