from typing import Optional

from flask import Request
from keycloak import KeycloakError, KeycloakOpenID

from simdb.config import Config

from ._authenticator import Authenticator
from ._exceptions import AuthenticationError
from ._user import User


class KeyCloakAuthenticator(Authenticator):
    TOKEN_HEADER_NAME = "KeyCloak-Token"
    Name = "KeyCloak"

    def authenticate(self, config: Config, request: Request) -> Optional[User]:
        sever_url = config.get_option("authentication.sever_url")
        realm_name = config.get_option("authentication.realm_name")
        client_id = config.get_option("authentication.client_id")

        token = request.headers.get(KeyCloakAuthenticator.TOKEN_HEADER_NAME, "")

        try:
            oid = KeycloakOpenID(
                server_url=sever_url, client_id=realm_name, realm_name=client_id
            )
            decoded = oid.decode_token(token)

            name = decoded.get("name", None)
            email = decoded.get("email", None)

            return User(name, email)
        except KeycloakError as err:
            raise AuthenticationError("Keycloak authentication error") from err
