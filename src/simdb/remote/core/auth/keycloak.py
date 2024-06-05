from typing import Optional
from flask import Request

from ....config import Config
from ._authenticator import Authenticator
from ._user import User
from ._exceptions import AuthenticationError


class KeyCloakAuthenticator(Authenticator):
    TOKEN_HEADER_NAME = "KeyCloak-Token"
    Name = "KeyCloak"

    def authenticate(
        self, config: Config, request: Request
    ) -> Optional[User]:
        from keycloak import KeycloakOpenID, KeycloakError

        sever_url = config.get_option("authentication.sever_url")
        realm_name = config.get_option("authentication.realm_name")
        client_id = config.get_option("authentication.client_id")

        token = request.headers.get(KeyCloakAuthenticator.TOKEN_HEADER_NAME, "")

        try:
            oid = KeycloakOpenID(server_url=sever_url, client_id=realm_name, realm_name=client_id)
            decoded = oid.decode_token(token)

            name = decoded['name'] if 'name' in decoded else None
            email = decoded['email'] if 'email' in decoded else None

            return User(name, email)
        except KeycloakError as err:
            raise AuthenticationError(f'Keycloak authentication error: {err.error_message}')
