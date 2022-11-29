from typing import Optional

from ....config import Config
from ._authenticator import Authenticator
from ._user import User
from ._exceptions import AuthenticationError


class LdapAuthenticator(Authenticator):
    """
    Authenticator for authenticating using an LDAP server.

    This requires the following extra parameters in the server configuration:
    ldap_server         - the URI of the LDAP server
    ldap_bind           - the bind string for the LDAP authentication (formatted to replace {username} with username)
    ldap_query_user     - the bind string for the LDAP query
    ldap_query_password - the password for the LDAP query
    ldap_query_base     - the base point for the LDAP query
    ldap_query_filter   - the filter to apply to the LDAP query (formatted to replace {username} with username)
    """

    Name = "LDAP"

    def authenticate(
        self, username: str, password: str, config: Config
    ) -> Optional[User]:
        import ldap

        ldap_host = config.get_option("server.ldap_server")
        try:
            conn = ldap.initialize(ldap_host)
        except ldap.LDAPError:
            raise AuthenticationError("failed to connect to ldap server")

        ldap_bind = config.get_option("server.ldap_bind")
        try:
            conn.simple_bind_s(ldap_bind.format(username=username), password)
        except ldap.INVALID_CREDENTIALS:
            return None

        conn.unbind_s()
        try:
            conn = ldap.initialize(ldap_host)
        except ldap.LDAPError:
            raise AuthenticationError("failed to connect to ldap server")

        ldap_query_user = config.get_option("server.ldap_query_user")
        ldap_query_password = config.get_option("server.ldap_query_password")

        try:
            conn.simple_bind_s(ldap_query_user, ldap_query_password)
        except ldap.INVALID_CREDENTIALS:
            raise AuthenticationError("failed to bind to LDAP server for user query")

        ldap_query_base = config.get_option("server.ldap_query_base")
        ldap_query_filter = config.get_option("server.ldap_query_filter")
        results = conn.search_s(
            ldap_query_base,
            ldap.SCOPE_SUBTREE,
            ldap_query_filter.format(username=username),
        )
        try:
            user = results[0][1]["uid"][0].decode()
            mail = results[0][1]["mail"][0].decode()
            return User(user, mail)
        except Exception:
            raise AuthenticationError("failed to find user in LDAP query")
