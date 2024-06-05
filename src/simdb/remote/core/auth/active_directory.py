from typing import Optional
from flask import Request

from ....config import Config
from ._authenticator import Authenticator
from ._user import User


class ActiveDirectoryAuthenticator(Authenticator):
    """
    Authenticator for authenticating using an LDAP server.

    This requires the following extra parameters in the server configuration:
    ad_server   -   the server URI
    ad_domain   -   the AD domain
    """

    Name = "ActiveDirectory"

    def authenticate(
        self, config: Config, request: Request
    ) -> Optional[User]:
        from easyad import EasyAD

        try:
            ad_config = {
                "AD_SERVER": config.get_option("authentication.ad_server"),
                "AD_DOMAIN": config.get_option("authentication.ad_domain"),
            }
            ad = EasyAD(ad_config)
        except (KeyError, ImportError):
            return None

        auth = request.authorization
        if not auth:
            return None

        username = auth.username
        password = auth.password

        user = ad.authenticate_user(username, password, json_safe=True)
        if user:
            return User(user["sAMAccountName"], user["mail"])
        else:
            return None
