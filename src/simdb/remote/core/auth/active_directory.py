from typing import Optional

from easyad import EasyAD
from flask import Request

from simdb.config import Config

from ._authenticator import Authenticator
from ._user import User


class ActiveDirectoryAuthenticator(Authenticator):
    """
    Authenticator for authenticating using an LDAP server.

    This requires the following extra parameters in the server configuration:
    ad_server   -   the server URI
    ad_domain   -   the AD domain
    ad_cert     -   path to the root ca certificate
    """

    Name = "ActiveDirectory"

    def authenticate(self, config: Config, request: Request) -> Optional[User]:
        try:
            ad_config = {
                "AD_SERVER": config.get_option("authentication.ad_server"),
                "AD_DOMAIN": config.get_option("authentication.ad_domain"),
                "AD_CA_CERT_FILE": config.get_option(
                    "authentication.ad_cert", default=""
                ),
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
