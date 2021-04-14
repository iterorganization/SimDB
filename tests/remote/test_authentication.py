import pytest
from unittest import mock
from simdb.remote import api
from simdb.config import Config


@mock.patch('simdb.config.Config.get_option')
def test_check_role(get_option):
    get_option.return_value = 'user1,"user2", user3'
    config = Config()
    ok = api.check_role(config, 'user1', 'test_role')
    assert ok
    get_option.assert_called_once_with('role.test_role.users', default='')
    ok = api.check_role(config, 'user4', None)
    assert ok
    ok = api.check_role(config, 'user4', 'test_role')
    assert not ok


@mock.patch('easyad.EasyAD')
@mock.patch('simdb.config.Config.get_option')
def test_check_auth(get_option, easy_ad):
    config = Config()
    get_option.side_effect = lambda a: {
        'server.admin_password': 'abc123',
        'server.ad_server': 'test.server',
        'server.ad_domain': 'test.domain',
    }[a]
    ok = api.check_auth(config, "admin", "abc123")
    assert ok
    get_option.assert_called_once_with('server.admin_password')

    easy_ad().authenticate_user.side_effect = lambda u, p, **k: u == "user" and p == "password"

    ok = api.check_auth(config, "user", "password")
    assert ok
    easy_ad.assert_called_with({
        'AD_SERVER': 'test.server',
        'AD_DOMAIN': 'test.domain',
    })
    easy_ad().authenticate_user.assert_called_once_with("user", "password", json_safe=True)

    ok = api.check_auth(config, "user", "wrong")
    assert not ok
