import pytest
from unittest import mock
from simdb.config import Config
try:
    import easyad
    has_easyad = True
except ImportError:
    has_easyad = False
try:
    import flask
    has_flask = True
except ImportError:
    has_flask = False


@mock.patch('simdb.config.Config.get_option')
@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_check_role(get_option):
    from simdb.remote import api
    from flask import Flask
    app = Flask('test')
    config = Config()
    app.simdb_config = config
    with app.app_context():
        get_option.return_value = 'user1,"user2", user3'
        ok = api.check_role(config, 'user1', 'test_role')
        assert ok
        get_option.assert_called_once_with('role.test_role.users', default='')
        ok = api.check_role(config, 'user4', None)
        assert ok
        ok = api.check_role(config, 'user4', 'test_role')
        assert not ok


@mock.patch('simdb.config.Config.get_option')
@pytest.mark.skipif(not has_easyad, reason="requires easyad library")
@pytest.mark.skipif(not has_flask, reason="requires flask library")
def test_check_auth(get_option):
    from simdb.remote import api
    patcher = mock.patch('easyad.EasyAD')
    easy_ad = patcher.start()

    config = Config()
    get_option.side_effect = lambda a: {
        'server.admin_password': 'abc123',
        'server.ad_server': 'test.server',
        'server.ad_domain': 'test.domain',
    }[a]
    ok = api.check_auth(config, "admin", "abc123")
    assert ok
    get_option.assert_called_once_with('server.admin_password')

    def auth(user, password, **kwargs):
        if user == "user" and password == "password":
            return {'dn': 'user', 'email': 'user@email.com'}
        return None
    easy_ad().authenticate_user.side_effect = auth

    ok = api.check_auth(config, "user", "password")
    assert ok
    easy_ad.assert_called_with({
        'AD_SERVER': 'test.server',
        'AD_DOMAIN': 'test.domain',
    })
    easy_ad().authenticate_user.assert_called_once_with("user", "password", json_safe=True)

    ok = api.check_auth(config, "user", "wrong")
    assert not ok
