from unittest import mock

from test_remote_api_version import _remote_api

from simdb.notifications import Notification


def test_watcher_requests_quote_sim_id():
    api = _remote_api()
    with mock.patch.object(api, "post") as post, mock.patch.object(
        api, "delete"
    ) as delete, mock.patch.object(api, "get") as get:
        get.return_value.json.return_value = []
        api.add_watcher("foo#1", "u", "u@iter.org", Notification.ALL)
        api.remove_watcher("100001/1?x", "u")
        api.list_watchers("a b")

    assert post.call_args.args[0] == "watchers/foo%231"
    assert delete.call_args.args[0] == "watchers/100001/1%3Fx"
    assert get.call_args.args[0] == "watchers/a%20b"
