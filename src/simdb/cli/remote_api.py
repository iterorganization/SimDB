import functools
import getpass
import gzip
import hashlib
import itertools
import json
from logging import fatal
import os
import pickle
import sys
import uuid
from collections import defaultdict
from collections.abc import Callable, Iterable
from io import BytesIO
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, ParamSpec, TypeVar, override
from urllib.parse import urlparse

import appdirs
import click
import requests
from requests.auth import AuthBase, HTTPBasicAuth
from semantic_version import Version

from file_transfer.http import FileTransferHandler, HttpFileTransferHandler
from file_transfer.rclone import RcloneFileTransferHandler
from simdb.config import Config
from simdb.database.models import Simulation
from simdb.imas.utils import SimDBUrl, imas_files
from simdb.json import CustomDecoder, CustomEncoder
from simdb.remote import CLIENT_API_VERSIONS, APIConstants

from .manifest import DataType

if TYPE_CHECKING:
    from simdb.database.models import File, Simulation, Watcher

if TYPE_CHECKING or "sphinx" in sys.modules:
    # Only importing these for type checking and documentation generation in order to
    # speed up runtime startup.
    import requests
    from requests.auth import AuthBase


class APIError(RuntimeError):
    pass


class FailedConnection(APIError):
    pass


class RemoteError(APIError):
    pass


P = ParamSpec("P")
R = TypeVar("R")


def try_request(func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapped_func(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except requests.ConnectionError as ex:
            url = ex.request.url if ex.request is not None else "undefined"
            raise FailedConnection(
                f"""\
Connection failed to {url}

Please check that the URL is valid and that SIMDB_REQUESTS_CA_BUNDLE is set if required.
                """
            ) from None
        except requests.HTTPError as ex:
            response_code = (
                ex.response.status_code if ex.response is not None else "undefined"
            )
            url = ex.request.url if ex.request is not None else "undefined"
            raise FailedConnection(
                f"HTTP error {response_code} returned from endpoint {url}."
            ) from None
        except requests.JSONDecodeError:
            raise FailedConnection(
                """\
Invalid JSON returned from request endpoint

This might indicate an invalid SimDB URL or the existence of a firewall.
                """
            ) from None

    return wrapped_func


def versioned_method(*versions: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Mark a RemoteAPI method that has version-specific implementations.

    The decorated function is the default implementation and serves the API versions
    passed here (e.g. "v1.3"). Register an alternative implementation for other versions
    with ``@<name>.register("v1.2")``; when the remote negotiates one of those versions,
    the registered function is called instead of the default::

        @versioned_method("v1.3")
        @try_request
        def push_simulation(self, ...):
            ...  # default implementation

        @push_simulation.register("v1.2")
        @try_request
        def _push_simulation_v1_2(self, ...):
            ...  # implementation used when the remote negotiates v1.2

    Methods that behave the same across every version they support simply omit the
    ``register`` calls and act as a plain version marker.

    Make the default (main) method the implementation for the latest
    supported version, and register overrides for the older versions it must stay
    compatible with. This keeps the current protocol as the primary, most-visible code
    path and confines backwards-compatibility handling to clearly named shims.

    The full set of supported versions is recorded on the method as ``_api_versions``,
    and calling the method with a negotiated version that no implementation serves
    raises a RemoteError. While no version has been negotiated yet, the default
    implementation is used.
    """

    def decorator(default: Callable[P, R]) -> Callable[P, R]:
        default_name = getattr(default, "__name__", repr(default))
        registry: dict[str, Callable[P, R]] = dict.fromkeys(versions, default)

        @functools.wraps(default)
        def wrapper(self, *args: P.args, **kwargs: P.kwargs) -> R:
            selected = getattr(self, "_api_version", None)
            if selected is None:
                return default(self, *args, **kwargs)
            impl = registry.get(selected)
            if impl is None:
                raise RemoteError(
                    f"'{default_name}' is not supported by the negotiated API "
                    + f"version '{selected}'. It requires one of: "
                    + f"{', '.join(sorted(registry))}."
                )
            return impl(self, *args, **kwargs)

        def register(*impl_versions: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
            def do_register(func: Callable[P, R]) -> Callable[P, R]:
                for version in impl_versions:
                    registry[version] = func
                # Keep the advertised version set in sync with the registry.
                wrapper._api_versions = frozenset(registry)  # ty: ignore[unresolved-attribute]
                return func

            return do_register

        wrapper._api_versions = frozenset(registry)  # ty: ignore[unresolved-attribute]
        wrapper.register = register  # ty: ignore[unresolved-attribute]
        return wrapper

    return decorator


def select_api_version(
    server_versions: Iterable[str],
    client_versions: Iterable[str] = CLIENT_API_VERSIONS,
) -> str | None:
    """
    Select the highest API version supported by both the server and this client.
    """
    common_versions = set(server_versions) & set(client_versions)
    if not common_versions:
        return None
    return max(common_versions, key=lambda v: Version.coerce(v.lstrip("v")))


def check_return(res: "requests.Response") -> None:
    if res.status_code != 200:
        try:
            data = res.json()
        except ValueError:
            data = {}
        if "error" in data:
            raise RemoteError(data["error"])
        else:
            res.raise_for_status()


def _get_paths(file: "File") -> Iterable[Path]:
    if file.type == DataType.FILE:
        if file.uri and file.uri.path:
            return [Path(file.uri.path)]
        return []
    else:
        return imas_files(file.uri)


class RemoteAPI:
    """
    Class to represent connection to remote API.

    This is used by the CLI to make all requests to the remote.
    """

    _remote: str
    _cookies: dict[str, str]
    _use_token: bool
    _firewall: str | None
    _server_auth: str
    _token: str
    _username: str | None
    _password: str | None

    def __init__(
        self,
        remote: str | None,
        username: str | None,
        password: str | None,
        config: Config,
        use_token: bool | None = None,
    ) -> None:
        """
        Create a new RemoteAPI.

        @param remote: the name of the remote - this is the name as created in the
                       configuration file. If not provided
        this will use the remote that has been marked as default.
        @param username: the username to use to authenticate with the remote - optional
                         if a token has been created for the remote.
        @param password: the password to used to authenticate with the remote - only
                         required if username is also provided.
        @param config: the CLI configuration object.
        @param use_token: override the default behaviour of only looking for a token if
                          username and password are not provided.
        """
        self._config: Config = config
        if not remote:
            remote = config.default_remote
        if not remote:
            raise KeyError(
                "Remote name not provided and no default remote found in config."
            )
        self._remote = remote
        try:
            self._url: str = config.get_string_option(f"remote.{remote}.url")
        except KeyError:
            raise ValueError(
                f"Remote '{remote}' not found. Use `simdb remote config add` to add it."
            ) from None

        self._firewall = config.get_string_option(
            f"remote.{remote}.firewall", default=None
        )

        if not username:
            username = config.get_string_option(f"remote.{remote}.username", default="")

        if use_token is not None:
            self._use_token = use_token
        else:
            token = config.get_option(f"remote.{remote}.token", default="")
            self._use_token = bool(token) or (not username and not password)

        if password and not username:
            raise ValueError(
                "Password given but no username given or found in configuration."
            )

        self._cookies = {}
        if self._firewall is not None:
            self._load_cookies(remote, username, password)

        self._api_url: str = f"{self._url}/"
        self._server_auth = self.get_server_authentication()
        if self._firewall:
            self._server_auth = "None"

        if username == "admin":
            self._server_auth = "admin-auth"

        if self._server_auth != "None" and not self._use_token:
            if not username:
                username = click.prompt("Username", default=getpass.getuser())
            if not password:
                password = click.prompt(
                    f"Password for user {username}", hide_input=True
                )

        self._token = config.get_string_option(f"remote.{remote}.token", default="")
        if self._server_auth != "None" and (self._use_token and not self._token):
            raise ValueError("No username or password given and no token found.")

        self._username = username
        self._password = password

        endpoints = self.get_endpoints()
        endpoint_versions = [endpoint.split("/")[-1] for endpoint in endpoints]

        selected_version = select_api_version(endpoint_versions)
        if selected_version is None:
            raise RemoteError(
                "No compatible API version found on remote: the server provides "
                + f"{', '.join(endpoint_versions) or 'none'} and this client supports "
                + f"{', '.join(CLIENT_API_VERSIONS)}."
            )

        if config.verbose:
            print(f"Selected API version {selected_version}")

        self._api_version = selected_version
        self._api_url += f"{selected_version}/"
        self.version = Version.coerce(self.get_api_version())
        self.server_version = Version.coerce(self.get_server_version())

    def _load_cookies(
        self, remote: str, username: str | None, password: str | None
    ) -> None:
        if self._firewall == "F5":
            headers = {"User-Agent": "it_script_basic"}
            cookies_file = f"{remote}-cookies.pkl"
            cookies_path = Path(appdirs.user_config_dir("simdb")) / cookies_file
            parsed_url = urlparse(self._url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

            cookies = None
            if cookies_path.exists():
                with cookies_path.open("rb") as f:
                    cookies = pickle.load(f)
                r = requests.get(f"{self._url}/", headers=headers, cookies=cookies)
                try:
                    # check to see if the cookies are still valid by trying a simple
                    # request
                    r.json()
                except requests.JSONDecodeError:
                    cookies = None

            if cookies is None:
                if not username:
                    username = click.prompt("Username", default=getpass.getuser())
                if not password:
                    password = click.prompt(
                        f"Password for user {username}", hide_input=True
                    )
                auth = (username, password)
                with requests.Session() as s:
                    s.headers["User-Agent"] = "it_script_basic"
                    p = s.post(f"{base_url}/my.policy", auth=auth)
                    if p.status_code != 200:
                        raise RuntimeError(
                            "Failed to get firewall authentication cookies"
                        )
                    cookies = s.cookies

                with cookies_path.open("wb") as f:
                    pickle.dump(cookies, f)
                cookies_path.chmod(0o600)

            if not cookies:
                raise RuntimeError("Failed to get firewall authentication cookies")
            self._cookies = cookies
        else:
            raise ValueError(f"Unknown firewall option {self._firewall}")

    @property
    def remote(self) -> str:
        """
        Return the name of the remote.
        """
        return self._remote

    def _get_auth(self) -> AuthBase:
        class JWTAuth(AuthBase):
            _token: str

            def __init__(self, token: str):
                self._token = token

            @override
            def __call__(
                self, request: requests.PreparedRequest
            ) -> requests.PreparedRequest:
                request.headers["Authorization"] = f"JWT-Token {self._token}"
                return request

        if self._use_token:
            return JWTAuth(self._token)
        else:
            return HTTPBasicAuth(self._username or "", self._password or "")

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        authenticate: bool | None = True,
        stream: bool | None = False,
    ) -> "requests.Response":
        """
        Perform an HTTP GET request.

        @param url: the URL of the request.
        @param params: any additional parameters to send along with the request.
        @param headers: additional headers to send with the request.
        @param authenticate: True if we should send authentication headers with the
                             request.
        @param stream: True to enable streaming.
        @return:
        """

        params = params if params is not None else {}
        headers = headers if headers is not None else {}
        headers["Accept-encoding"] = "gzip"
        headers["User-Agent"] = "it_script_basic"

        # Get token api expected basic auth in request
        if authenticate and self._server_auth != "None":
            res = requests.get(
                self._api_url + url,
                params=params,
                auth=self._get_auth(),
                headers=headers,
                cookies=self._cookies,
                stream=stream,
            )
        else:
            res = requests.get(
                self._api_url + url,
                params=params,
                headers=headers,
                cookies=self._cookies,
                stream=stream,
            )

        check_return(res)
        return res

    def put(self, url: str, data: dict, **kwargs) -> "requests.Response":
        """
        Perform an HTTP PUT request.

        @param url: the URL of the request.
        @param data: the PUT data to send.
        @param kwargs: any additional keyword arguments to add to the request.
        @return:
        """

        headers = {"Content-type": "application/json"}
        headers["User-Agent"] = "it_script_basic"

        if self._server_auth != "None":
            res = requests.put(
                self._api_url + url,
                data=json.dumps(data, cls=CustomEncoder),
                headers=headers,
                auth=self._get_auth(),
                cookies=self._cookies,
                **kwargs,
            )
        else:
            res = requests.put(
                self._api_url + url,
                data=json.dumps(data, cls=CustomEncoder),
                headers=headers,
                cookies=self._cookies,
                **kwargs,
            )

        check_return(res)
        return res

    def post(self, url: str, data: dict, **kwargs) -> "requests.Response":
        """
        Perform an HTTP POST request.

        @param url: the URL of the request.
        @param data: the POST data to send.
        @param kwargs: any additional keyword arguments to add to the request.
        @return:
        """

        if "files" in kwargs:
            if data:
                raise Exception("Cannot send JSON data at the same time as files.")
            headers = {}
        else:
            headers = {"Content-type": "application/json"}
        post_data = json.dumps(data, cls=CustomEncoder, indent=2) if data else {}
        headers["User-Agent"] = "it_script_basic"

        # Compress the data if it is larger than 2 MB and the URL is for simulations
        if (
            url == "simulations"
            and isinstance(post_data, str)
            and len(post_data) > 2 * 1024 * 1024
        ):
            buf = BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
                gz.write(post_data.encode("utf-8"))
            post_data = buf.getvalue()
            headers["Content-Encoding"] = "gzip"
            headers["Content-Type"] = "application/json"

        if self._server_auth != "None":
            res = requests.post(
                self._api_url + url,
                data=post_data,
                headers=headers,
                auth=self._get_auth(),
                cookies=self._cookies,
                **kwargs,
            )
        else:
            res = requests.post(
                self._api_url + url,
                data=post_data,
                headers=headers,
                cookies=self._cookies,
                **kwargs,
            )

        check_return(res)
        return res

    def patch(self, url: str, data: dict, **kwargs) -> "requests.Response":
        """
        Perform an HTTP PATCH request.

        @param url: the URL of the request.
        @param data: the PATCH data to send.
        @param kwargs: any additional keyword arguments to add to the request.
        @return:
        """

        headers = {"Content-type": "application/json"}
        headers["User-Agent"] = "it_script_basic"

        if self._server_auth != "None":
            res = requests.patch(
                self._api_url + url,
                data=json.dumps(data, cls=CustomEncoder),
                headers=headers,
                auth=self._get_auth(),
                cookies=self._cookies,
                **kwargs,
            )
        else:
            res = requests.patch(
                self._api_url + url,
                data=json.dumps(data, cls=CustomEncoder),
                headers=headers,
                cookies=self._cookies,
                **kwargs,
            )

        check_return(res)
        return res

    def delete(self, url: str, data: dict[str, Any], **kwargs) -> "requests.Response":
        """
        Perform an HTTP DELETE request.

        @param url: the URL of the request.
        @param data: the DELETE data to send.
        @param kwargs: any additional keyword arguments to add to the request.
        @return:
        """

        headers = {"Content-type": "application/json"}
        headers["User-Agent"] = "it_script_basic"

        if self._server_auth != "None":
            res = requests.delete(
                self._api_url + url,
                data=json.dumps(data, cls=CustomEncoder),
                headers=headers,
                auth=self._get_auth(),
                cookies=self._cookies,
                **kwargs,
            )
        else:
            res = requests.delete(
                self._api_url + url,
                data=json.dumps(data, cls=CustomEncoder),
                headers=headers,
                cookies=self._cookies,
                **kwargs,
            )
        check_return(res)
        return res

    def has_url(self) -> bool:
        return bool(self._url)

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_token(self) -> str:
        res = self.get("token")
        data = res.json()
        return data["token"]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_endpoints(self) -> list[str]:
        res = self.get("", authenticate=False)
        data = res.json()
        return data["endpoints"]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_server_authentication(self) -> str:
        res = self.get("", authenticate=False)
        data = res.json()
        return data.get("authentication")

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_api_version(self) -> str:
        res = self.get("", authenticate=False)
        data = res.json()
        return data["api_version"]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_server_version(self) -> str:
        res = self.get("", authenticate=False)
        data = res.json()
        return data["server_version"]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_validation_schemas(self) -> list[dict]:
        res = self.get("validation_schema")
        return res.json()

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_upload_options(self) -> dict[str, Any]:
        try:
            res = self.get("upload_options")
            return res.json()
        except FailedConnection:
            # old remotes may not provide this endpoint
            return {}

    @versioned_method("v1.3")
    @try_request
    def get_file_transfer_options(self) -> dict[str, Any]:
        try:
            res = self.get("file_transfer_options")
            return res.json()
        except FailedConnection:
            # old remotes may not provide this endpoint
            return {
                "available_transfer_types": ["HTTP"],
                "transfer_options": {"HTTP": {}},
            }

    @versioned_method("v1.2", "v1.3")
    @try_request
    def list_simulations(
        self, meta: list[str] | None = None, limit: int = 0
    ) -> list["Simulation"]:
        args = "?" + "&".join(meta) if meta else ""
        headers = {"simdb-result-limit": str(limit)}
        res = self.get("simulations" + args, headers=headers)
        data = res.json(cls=CustomDecoder)
        return [Simulation.from_data(sim) for sim in data["results"]]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_simulation(self, sim_id: str) -> "Simulation":
        res = self.get("simulation/" + sim_id)
        return Simulation.from_data(res.json(cls=CustomDecoder))

    @versioned_method("v1.2", "v1.3")
    @try_request
    def trace_simulation(self, sim_id: str) -> dict:
        res = self.get("trace/" + sim_id)
        return res.json(cls=CustomDecoder)

    @versioned_method("v1.2", "v1.3")
    @try_request
    def query_simulations(
        self, constraints: list[str], meta: list[str], limit=0
    ) -> list["Simulation"]:
        params = defaultdict(list)
        for item in constraints:
            (key, value) = item.split("=")
            params[key].append(value)
        args = "?" + "&".join(meta) if meta else ""
        headers = {
            APIConstants.LIMIT_HEADER: str(limit),
            APIConstants.PAGE_HEADER: str(1),
        }
        res = self.get("simulations" + args, params, headers=headers)
        data = res.json(cls=CustomDecoder)
        return [Simulation.from_data(sim) for sim in data["results"]]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def delete_simulation(self, sim_id: str) -> dict:
        res = self.delete("simulation/" + sim_id, {})
        return res.json()

    @versioned_method("v1.2", "v1.3")
    @try_request
    def update_simulation(self, sim_id: str, update_type: "Simulation.Status") -> None:
        self.patch("simulation/" + sim_id, {"status": update_type.value})

    @versioned_method("v1.2", "v1.3")
    @try_request
    def validate_simulation(self, sim_id: str) -> tuple[bool, str]:
        res = self.post("validate/" + sim_id, {})
        data = res.json()
        if data["passed"]:
            return True, ""
        else:
            return False, data["error"]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def add_watcher(
        self, sim_id: str, user: str, email: str, notification: "Watcher.Notification"
    ) -> None:
        self.post(
            "watchers/" + sim_id,
            {"user": user, "email": email, "notification": notification.name},
        )

    @versioned_method("v1.2", "v1.3")
    @try_request
    def remove_watcher(self, sim_id: str, user: str) -> None:
        self.delete("watchers/" + sim_id, {"user": user})

    @versioned_method("v1.2", "v1.3")
    @try_request
    def list_watchers(self, sim_id: str) -> list[tuple]:
        res = self.get("watchers/" + sim_id)
        return [(d["username"], d["email"], d["notification"]) for d in res.json()]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def set_metadata(
        self, sim_id: str, key: str, value: str | uuid.UUID | int | float
    ) -> list[str]:
        res = self.patch("simulation/metadata/" + sim_id, {"key": key, "value": value})
        return [data["value"] for data in res.json()]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def delete_metadata(self, sim_id: str, key: str) -> list[str]:
        res = self.delete("simulation/metadata/" + sim_id, {"key": key})
        return [data["value"] for data in res.json()]

    @versioned_method("v1.3")
    @try_request
    def get_simulation_data(
        self, sim_id: str, path: str, dd_version: str | None = None
    ) -> dict[str, Any]:
        params = {"path": path}
        if dd_version is not None:
            params["dd_version"] = dd_version
        res = self.get(f"simulation/{sim_id}/data", params=params)
        return res.json()

    @try_request
    def get_directory(self) -> str:
        res = self.get("staging_dir")
        return res.json()["staging_dir"]

    def _send_file(
        self,
        handler: FileTransferHandler,
        simulation: Simulation,
        sim_data: dict[str, Any],
        file: File,
        copy_ids: bool,
        out_stream: IO[str],
        file_type: str,
    ) -> None:
        if file.type == DataType.IMAS:
            if not copy_ids:
                print(f"Skipping IDS data {file}", file=out_stream, flush=True)
                return
            ids_list = simulation.meta_dict().get("input_ids", [])
            for path in imas_files(file.uri):
                # Check if hdf5 ids_name is in ids_list
                ids_name = Path(path).name.split(".")
                if ids_name[1] == "h5" and (
                    ids_name[0] != "master"
                    and ids_list is not None
                    and ids_name[0] not in ids_list
                ):
                    continue
                sim_file = next(
                    f for f in sim_data[file_type + "s"] if f.get("uuid") == file.uuid
                )
                sim_file["uri"] = f"file:{path}"
                handler.send_file(
                    path,
                    file.uuid,
                    file_type,
                    sim_data,
                    out_stream,
                    file.type,
                )

            _ = self.post(
                "files",
                data={
                    "simulation": simulation.data(recurse=True),
                    "obj_type": file.type,
                    "files": [
                        {
                            "file_type": file_type,
                            "file_uuid": file.uuid.hex,
                            "ids_list": ids_list,
                        }
                    ],
                },
            )

        else:
            if file.uri and file.uri.path:
                handler.send_file(
                    Path(file.uri.path),
                    file.uuid,
                    file_type,
                    sim_data,
                    out_stream,
                    file.type,
                )

    @versioned_method("v1.2", "v1.3")
    @try_request
    def push_simulation(
        self,
        simulation: "Simulation",
        out_stream: IO[str] = sys.stdout,
        add_watcher: bool = True,
    ) -> None:
        """
        Push the local simulation to the remote server.

        First we upload any files associated with the simulation, then push the
        simulation metadata.

        :param simulation: The Simulation to push to remote server
        :param out_stream: The IO stream to write messages to the user (default: stdout)
        :param add_watcher: Add the current user as a watcher of the simulation on the
                            remote server
        """

        sim_data = simulation.data(recurse=True, no_meta=True)

        upload_options = self.get_upload_options()
        available_transfer_types = upload_options["available_transfer_types"]

        transfer_handlers: dict[str, type[FileTransferHandler]] = {
            "HTTP": HttpFileTransferHandler,
            "RCLONE": RcloneFileTransferHandler,
        }

        handler = None
        for transfer_type in available_transfer_types:
            if transfer_type not in transfer_handlers:
                continue
            file_transfer_options = upload_options["transfer_options"][transfer_type]
            handler = transfer_handlers[transfer_type](self, **file_transfer_options)
            break

        if handler is None:
            raise ValueError("No file transfer handler available")

        if upload_options.get("copy_files", True):
            copy_ids = upload_options.get("copy_ids", True)

            for file in simulation.inputs:
                self._send_file(
                    handler, simulation, sim_data, file, copy_ids, out_stream, "input"
                )

            for file in simulation.outputs:
                self._send_file(
                    handler, simulation, sim_data, file, copy_ids, out_stream, "output"
                )

        sim_data = simulation.data(recurse=True)
        uploaded_by = simulation.meta_dict().get("uploaded_by", None)
        print("Uploading simulation data ... ", file=out_stream, end="", flush=True)
        _ = self.post(
            "simulations",
            data={
                "simulation": sim_data,
                "add_watcher": add_watcher,
                "uploaded_by": uploaded_by,
            },
        )
        print("Success", file=out_stream, flush=True)

    def _get_file_info(self, uuid: uuid.UUID) -> list[tuple[Path, str]]:
        r = self.get(f"file/{uuid.hex}")
        data = r.json()
        files = data["files"]
        return [(Path(file["path"]), file["checksum"]) for file in files]

    def _pull_file(
        self,
        uuid: uuid.UUID,
        index: int,
        checksum: str,
        from_path: Path,
        to_path: Path,
        out_stream: IO[str],
    ):
        msg = f"Downloading file {from_path} to {to_path}"
        print(
            msg,
            file=out_stream,
            flush=True,
        )
        response = self.get(f"file/download/{uuid.hex}/{index}", stream=True)

        to_path.parent.mkdir(parents=True, exist_ok=True)
        sha1 = hashlib.sha1()

        with to_path.open("wb") as f:
            total_length = response.headers.get("content-length")
            if total_length is None:
                f.write(response.content)
            else:
                downloaded = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    sha1.update(data)
                    downloaded += len(data)
                    f.write(data)
                    done = int(50 * downloaded / total_length)
                    print(
                        "\r[{}{}] {:0.2f}%".format(
                            "=" * done,
                            " " * (50 - done),
                            100.0 * (downloaded / total_length),
                        ),
                        file=out_stream,
                        end="",
                        flush=True,
                    )
                print("\r", file=out_stream, end="", flush=True)

        if sha1.hexdigest() != checksum:
            raise APIError(f"Checksum failed for file {from_path}")

    @versioned_method("v1.2", "v1.3")
    @try_request
    def pull_simulation(
        self, sim_id: str, directory: Path, out_stream: IO[str] = sys.stdout
    ) -> "Simulation":
        """
        Pull the simulation from the remote server.

        This involves downloading all the files associated with the simulation into the
        provided simulation directory.

        :param sim_id: The id of the Simulation to pull
        :param directory: The local directory to use as the root directory of the
                          simulation
        :param out_stream: The IO stream to write messages to the user (default: stdout)
        """
        simulation = self.get_simulation(sim_id)
        if simulation is None:
            raise RemoteError(f"Failed to find simulation: {sim_id}")

        all_paths = []

        for file in itertools.chain(simulation.inputs, simulation.outputs):
            info = self._get_file_info(file.uuid)
            all_paths += [path for (path, _) in info]

        common_root = os.path.commonpath(all_paths)

        for file in itertools.chain(simulation.inputs, simulation.outputs):
            info = self._get_file_info(file.uuid)

            if file.type == DataType.FILE:
                (path, checksum) = info[0]
                rel_path = directory / path.relative_to(common_root)
                self._pull_file(file.uuid, 0, checksum, path, rel_path, out_stream)
                file.uri = SimDBUrl.build(
                    scheme="file", path=rel_path.absolute().as_posix()
                )
            elif file.type == DataType.IMAS:
                for index, (path, checksum) in enumerate(info):
                    rel_path = directory / path.relative_to(common_root)
                    self._pull_file(
                        file.uuid, index, checksum, path, rel_path, out_stream
                    )

                qs = dict(file.uri.query_params())
                to_path = (
                    directory / Path(qs.get("path", "")).relative_to(common_root)
                ).absolute()
                backend = qs.get("backend")
                file.uri = SimDBUrl.build(
                    scheme="imas", path=backend, query=f"path={to_path}"
                )

        return simulation

    @versioned_method("v1.2", "v1.3")
    @try_request
    def reset_database(self) -> None:
        self.post("reset", {})
