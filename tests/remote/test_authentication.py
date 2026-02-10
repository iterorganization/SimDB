import importlib
from typing import ClassVar
from unittest import mock

import pytest

from simdb.config import Config
from simdb.remote.core.auth import User, check_auth, check_role

has_easyad = importlib.util.find_spec("easyad") is not None
has_flask = importlib.util.find_spec("flask") is not None
if has_flask:
    from flask import Flask


@mock.patch("simdb.config.Config.get_option")
@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_check_role(get_string_option):
    app = Flask("test")
    config = Config()
    app.simdb_config = config
    with app.app_context():
        get_string_option.return_value = 'user1,"user2", user3'
        ok = check_role(config, User("user1", ""), "test_role")
        assert ok
        get_string_option.assert_called_with("role.test_role.users", "")
        ok = check_role(config, User("user4", ""), None)
        assert ok
        ok = check_role(config, User("user4", ""), "test_role")
        assert not ok


@mock.patch("simdb.remote.core.auth.active_directory.EasyAD")
@mock.patch("simdb.config.Config.get_option")
@pytest.mark.skipif(not has_easyad, reason="requires easyad library")
@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_check_auth(get_option, easy_ad):
    config = Config()
    get_option.side_effect = lambda name, default=None: {
        "server.admin_password": "abc123",
        "authentication.type": "ActiveDirectory",
        "authentication.ad_server": "test.server",
        "authentication.ad_domain": "test.domain",
        "authentication.ad_cert": "test.cert",
    }.get(name, default)

    class request:
        class authorization:
            username = ""
            password = ""

        headers: ClassVar[dict] = {}

    request.authorization.username = "admin"
    request.authorization.password = "abc123"
    ok = check_auth(config, request)
    assert ok
    get_option.assert_called_once_with("server.admin_password")

    def auth(user, password, **kwargs):
        if user == "user" and password == "password":
            return {"sAMAccountName": "user", "mail": "user@email.com"}
        return None

    easy_ad.return_value.authenticate_user.side_effect = auth
    request.authorization.username = "user"
    request.authorization.password = "password"
    ok = check_auth(config, request)
    assert ok
    easy_ad.assert_called_with(
        {
            "AD_SERVER": "test.server",
            "AD_DOMAIN": "test.domain",
            "AD_CA_CERT_FILE": "test.cert",
        }
    )
    easy_ad.return_value.authenticate_user.assert_called_once_with(
        "user", "password", json_safe=True
    )
    request.authorization.username = "user"
    request.authorization.password = "wrong"
    request.headers = {"Authorization": ""}
    ok = check_auth(config, request)
    assert not ok
