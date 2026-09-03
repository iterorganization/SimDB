"""Tests for the HTTP layer of :class:`simdb.cli.remote_api.RemoteAPI`.

The other CLI tests stub ``RemoteAPI`` methods so they can concentrate on the
commands. Here it is the client itself that is under test, so only ``requests``
is replaced: construction, authentication, URL building, error translation and
response parsing all run for real.
"""

import json
from unittest import mock

import pytest
import requests
from pydantic import ValidationError

from simdb.cli.remote_api import (
    FailedConnection,
    RemoteAPI,
    RemoteError,
    check_return,
    try_request,
)
from simdb.config import Config
from simdb.remote.models import TokenResponse

INDEX = {
    "api": "SimDB",
    "api_version": "1.3",
    "server_version": "0.11",
    "endpoints": ["http://remote.test/v1.2", "http://remote.test/v1.3"],
    "authentication": "None",
}


def response(payload=None, status=200, content=None) -> requests.Response:
    """Build a real :class:`requests.Response` around a JSON payload."""
    res = requests.Response()
    res.status_code = status
    res.url = "http://remote.test/"
    res.reason = "OK" if status == 200 else "Error"
    if content is None:
        content = json.dumps(payload if payload is not None else {}).encode()
    res._content = content
    return res


class FakeHttp:
    """Answer ``requests.get``/``post`` from a URL suffix to payload mapping."""

    def __init__(self, index=None):
        self.routes = {"": index if index is not None else dict(INDEX)}
        self.calls = []

    def route(self, suffix, payload=None, status=200, content=None):
        self.routes[suffix] = response(payload, status=status, content=content)

    def _respond(self, method, url, **kwargs):
        self.calls.append(mock.call(method, url, **kwargs))
        suffix = url.split("/v1.3/", 1)[-1] if "/v1.3/" in url else ""
        if url.rstrip("/") in ("http://remote.test", "http://remote.test/"):
            suffix = ""
        route = self.routes.get(suffix)
        if route is None:
            return response({"error": f"no route for {url!r}"}, status=404)
        return route if isinstance(route, requests.Response) else response(route)

    def request_for(self, suffix):
        """The recorded call whose URL ends with the given suffix."""
        for call in self.calls:
            if call.args[1].endswith(suffix):
                return call
        raise AssertionError(f"no request was made to {suffix!r}")


@pytest.fixture
def http(monkeypatch):
    fake = FakeHttp()
    for method in ("get", "post", "put", "delete"):
        monkeypatch.setattr(
            requests,
            method,
            lambda url, _method=method, **kwargs: fake._respond(_method, url, **kwargs),
        )
    return fake


def make_config(**options) -> Config:
    config = Config()
    config.set_option("remote.test.url", "http://remote.test")
    for name, value in options.items():
        config.set_option(f"remote.test.{name}", value)
    return config


# ---------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------


def test_the_negotiated_version_is_used_for_requests(http):
    api = RemoteAPI("test", None, None, make_config())

    assert api._api_url == "http://remote.test/v1.3/"
    assert api.remote == "test"
    assert api.has_url() is True


def test_the_default_remote_is_used_when_no_name_is_given(http):
    config = make_config()
    config.default_remote = "test"

    api = RemoteAPI(None, None, None, config)

    assert api.remote == "test"


def test_a_missing_remote_name_without_a_default_is_reported(http):
    with pytest.raises(KeyError, match="no default remote"):
        RemoteAPI(None, None, None, Config())


def test_an_unknown_remote_is_reported(http):
    with pytest.raises(ValueError, match="Remote 'other' not found"):
        RemoteAPI("other", None, None, make_config())


def test_a_password_without_a_username_is_rejected(http):
    with pytest.raises(ValueError, match="Password given but no username"):
        RemoteAPI("test", None, "secret", make_config())


def test_authentication_without_credentials_or_a_token_is_rejected(http):
    http.routes[""] = response({**INDEX, "authentication": "LDAP"})

    with pytest.raises(ValueError, match="No username or password given"):
        RemoteAPI("test", None, None, make_config())


def test_a_remote_without_a_usable_version_is_reported(http):
    http.routes[""] = response({**INDEX, "endpoints": ["http://remote.test/v9"]})

    with pytest.raises(RemoteError, match="No compatible API version"):
        RemoteAPI("test", None, None, make_config())


def test_a_remote_that_reports_no_api_version_is_reported(http):
    http.routes[""] = response({**INDEX, "api_version": None})

    with pytest.raises(RemoteError, match="did not report an API version"):
        RemoteAPI("test", None, None, make_config())


def test_a_remote_that_reports_no_server_version_is_reported(http):
    http.routes[""] = response({**INDEX, "server_version": None})

    with pytest.raises(RemoteError, match="did not report a server version"):
        RemoteAPI("test", None, None, make_config())


def test_the_selected_version_is_announced_when_verbose(http, capsys):
    config = make_config()
    config.verbose = True

    RemoteAPI("test", None, None, config)

    assert "Selected API version v1.3" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# authentication
# ---------------------------------------------------------------------------


def test_no_credentials_are_sent_to_an_unauthenticated_remote(http):
    api = RemoteAPI("test", None, None, make_config())
    http.route("validation_schema", [])

    api.get_validation_schemas()

    assert "auth" not in http.request_for("validation_schema").kwargs


def test_a_token_is_sent_as_a_jwt_header(http):
    http.routes[""] = response({**INDEX, "authentication": "LDAP"})
    api = RemoteAPI("test", None, None, make_config(token="123ABC"))
    http.route("validation_schema", [])

    api.get_validation_schemas()

    auth = http.request_for("validation_schema").kwargs["auth"]
    request = auth(mock.Mock(headers={}))
    assert request.headers["Authorization"] == "JWT-Token 123ABC"


def test_a_username_and_password_are_sent_as_basic_auth(http):
    http.routes[""] = response({**INDEX, "authentication": "LDAP"})
    api = RemoteAPI("test", "user", "secret", make_config())
    http.route("validation_schema", [])

    api.get_validation_schemas()

    assert http.request_for("validation_schema").kwargs["auth"] == ("user", "secret")


def test_credentials_are_prompted_for_when_the_remote_authenticates(http):
    http.routes[""] = response({**INDEX, "authentication": "LDAP"})

    with mock.patch("click.prompt", side_effect=["user", "secret"]) as prompt:
        api = RemoteAPI("test", None, None, make_config(), use_token=False)

    assert prompt.call_count == 2
    assert api._username == "user"
    assert api._password == "secret"


# ---------------------------------------------------------------------------
# requests and responses
# ---------------------------------------------------------------------------


def test_requests_are_sent_to_the_versioned_url(http):
    api = RemoteAPI("test", None, None, make_config())
    http.route("token", {"token": "NEWTOKEN"})

    assert api.get_token() == "NEWTOKEN"
    assert http.request_for("token").args[1] == "http://remote.test/v1.3/token"


def test_the_api_version_context_redirects_requests(http):
    api = RemoteAPI("test", None, None, make_config())
    http.route("validation_schema", [])

    with api.api_version("v1.2"):
        assert api._api_url == "http://remote.test/v1.2/"

    assert api._api_url == "http://remote.test/v1.3/"


def test_list_simulations_sends_the_pagination_headers(http):
    api = RemoteAPI("test", None, None, make_config())
    http.route(
        "simulations",
        {
            "count": 1,
            "page": 1,
            "limit": 10,
            "results": [
                {
                    "uuid": {"_type": "uuid.UUID", "hex": "0" * 32},
                    "alias": "sim",
                    "datetime": "2000-01-01",
                }
            ],
        },
    )

    simulations = api.list_simulations(limit=10)

    assert [simulation.alias for simulation in simulations] == ["sim"]
    headers = http.request_for("simulations").kwargs["headers"]
    assert headers["simdb-result-limit"] == "10"


def test_list_simulations_appends_the_requested_metadata(http):
    api = RemoteAPI("test", None, None, make_config())
    http.route(
        "simulations?pulse&run", {"count": 0, "page": 1, "limit": 0, "results": []}
    )

    api.list_simulations(meta=["pulse", "run"])

    assert http.request_for("simulations?pulse&run")


def test_an_error_payload_becomes_a_remote_error(http):
    api = RemoteAPI("test", None, None, make_config())
    http.route("validation_schema", {"error": "you shall not pass"}, status=403)

    with pytest.raises(RemoteError, match="you shall not pass"):
        api.get_validation_schemas()


def test_an_error_without_a_payload_becomes_a_failed_connection(http):
    api = RemoteAPI("test", None, None, make_config())
    http.route("validation_schema", status=500, content=b"<html>oops</html>")

    with pytest.raises(FailedConnection, match="HTTP error 500"):
        api.get_validation_schemas()


def test_a_non_json_response_becomes_a_failed_connection(http):
    """A firewall login page is HTML where the API promised JSON."""
    api = RemoteAPI("test", None, None, make_config())
    http.route("validation_schema", content=b"<html>login</html>")

    with pytest.raises(FailedConnection, match="Invalid JSON"):
        api.get_validation_schemas()


def test_unexpected_json_becomes_a_remote_error(http):
    api = RemoteAPI("test", None, None, make_config())
    http.route("token", {"not_a_token": True})

    with pytest.raises(RemoteError, match="Unexpected data exchanged"):
        api.get_token()


# ---------------------------------------------------------------------------
# check_return and try_request, tested on their own
# ---------------------------------------------------------------------------


def test_check_return_accepts_a_successful_response():
    assert check_return(response({"ok": True})) is None


def test_check_return_raises_for_status_without_an_error_field():
    with pytest.raises(requests.HTTPError):
        check_return(response({"detail": "nope"}, status=404))


def test_try_request_translates_a_connection_error():
    request = mock.Mock(url="http://remote.test/v1.3/simulations")

    @try_request
    def failing():
        raise requests.ConnectionError(request=request)

    with pytest.raises(FailedConnection, match="Connection failed to"):
        failing()


def test_try_request_reports_an_unknown_url_for_a_request_less_error():
    @try_request
    def failing():
        raise requests.ConnectionError(request=None)

    with pytest.raises(FailedConnection, match="undefined"):
        failing()


def test_try_request_translates_a_json_decode_error():
    @try_request
    def failing():
        raise requests.JSONDecodeError("bad", "doc", 0)

    with pytest.raises(FailedConnection, match="Invalid JSON"):
        failing()


def test_try_request_translates_a_validation_error():
    @try_request
    def failing():
        TokenResponse.model_validate({"wrong": "shape"})

    with pytest.raises(RemoteError, match="Unexpected data exchanged"):
        failing()


def test_try_request_passes_a_successful_call_through():
    @try_request
    def succeeding(value):
        return value

    assert succeeding(42) == 42


def test_a_validation_error_is_not_swallowed_as_something_else():
    """Only ``json_invalid`` errors mean the response was not JSON at all."""
    with pytest.raises(ValidationError):
        TokenResponse.model_validate_json(b"{}")
