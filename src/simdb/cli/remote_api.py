import os
import json
import uuid
from typing import (
    List,
    Dict,
    Callable,
    Tuple,
    IO,
    Iterable,
    Optional,
    Union,
    TYPE_CHECKING,
    Any,
)
import gzip
import io
import sys
import click
import itertools
import hashlib
import appdirs
import pickle
import getpass
from urllib.parse import urlparse
from pathlib import Path
from semantic_version import Version

from .manifest import DataObject
from ..config import Config
from ..json import CustomDecoder, CustomEncoder
from ..imas.utils import imas_files

if TYPE_CHECKING:
    from ..database.models import Simulation, Watcher, File

if TYPE_CHECKING or "sphinx" in sys.modules:
    # Only importing these for type checking and documentation generation in order to speed up runtime startup.
    import requests
    from requests.auth import AuthBase


class APIError(RuntimeError):
    pass


class FailedConnection(APIError):
    pass


class RemoteError(APIError):
    pass


def try_request(func: Callable) -> Callable:
    def wrapped_func(*args, **kwargs):
        import requests

        try:
            return func(*args, **kwargs)
        except requests.ConnectionError as ex:
            raise FailedConnection(
                f"""\
Connection failed to {ex.request.url}

Please check that the URL is valid and that SIMDB_REQUESTS_CA_BUNDLE is set if required.
                """
            )
        except requests.HTTPError as ex:
            raise FailedConnection(
                f"""\
HTTP error {ex.response.status_code} returned from endpoint {ex.request.url}
                """
            )
        except requests.JSONDecodeError:
            raise FailedConnection(
                """\
Invalid JSON returned from request endpoint

This might indicate an invalid SimDB URL or the existence of a firewall.
                """
            )

    return wrapped_func


def read_bytes(path: str, compressed: bool = True) -> bytes:
    if compressed:
        with io.BytesIO() as buffer:
            with gzip.GzipFile(fileobj=buffer, mode="wb") as gz_file:
                with open(path, "rb") as file_in:
                    gz_file.write(file_in.read())
            buffer.seek(0)
            return buffer.read()
    else:
        with open(path, "rb") as file:
            return file.read()


def _read_bytes_in_chunks(
        path: Path, compressed: bool = True, chunk_size: int = 1024
) -> Iterable[bytes]:
    with path.open("rb") as file_in:
        while True:
            if compressed:
                with io.BytesIO() as buffer:
                    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz_file:
                        data = file_in.read(chunk_size)
                        if not data:
                            break
                        gz_file.write(data)
                    buffer.seek(0)
                    yield buffer.read()
            else:
                data = file_in.read(chunk_size)
                if not data:
                    break
                yield data


def check_return(res: "requests.Response") -> None:
    if res.status_code != 200:
        try:
            data = res.json()
        except json.JSONDecodeError:
            data = {}
        if "error" in data:
            raise RemoteError(data["error"])
        else:
            res.raise_for_status()


def _get_paths(file: "File") -> Iterable[Path]:
    if file.type == DataObject.Type.FILE:
        return [file.uri.path]
    else:
        return imas_files(file.uri)


class RemoteAPI:
    """
    Class to represent connection to remote API.

    This is used by the CLI to make all requests to the remote.
    """

    _remote: str

    def __init__(
            self,
            remote: Optional[str],
            username: Optional[str],
            password: Optional[str],
            config: Config,
            use_token: Optional[bool] = None,
    ) -> None:
        """
        Create a new RemoteAPI.

        @param remote: the name of the remote - this is the name as created in the configuration file. If not provided
        this will use the remote that has been marked as default.
        @param username: the username to use to authenticate with the remote - optional if a token has been created for
        the remote.
        @param password: the password to used to authenticate with the remote - only required if username is also
        provided.
        @param config: the CLI configuration object.
        @param use_token: override the default behaviour of only looking for a token if username and password are not
        provided.
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
            self._url: str = config.get_option(f"remote.{remote}.url")
        except KeyError:
            raise ValueError(
                f"Remote '{remote}' not found. Use `simdb remote config add` to add it."
            )

        self._api_url: str = f"{self._url}/v{config.api_version}/"
        self._firewall: Optional[str] = config.get_option(
            f"remote.{remote}.firewall", default=None
        )

        if not username:
            username = config.get_option(f"remote.{remote}.username", default="")

        if use_token is not None:
            self._use_token = use_token
        else:
            token = config.get_option(f"remote.{remote}.token", default="")
            self._use_token = token or (not username and not password)

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

        if self._server_auth != "None" and not self._use_token:
            if not username:
                username = click.prompt("Username", default=getpass.getuser())
            if not password:
                password = click.prompt(
                    f"Password for user {username}", hide_input=True
                )

        self._token = config.get_option(f"remote.{remote}.token", default="")
        if self._server_auth != "None" and (self._use_token and not self._token):
            raise ValueError("No username or password given and no token found.")

        self._username = username
        self._password = password

        endpoints = self.get_endpoints()
        endpoint_versions = [endpoint.split("/")[-1] for endpoint in endpoints]

        if not endpoint_versions:
            raise RemoteError("No compatible API version found on remote")

        latest_version = max(endpoint_versions)
        if config.verbose:
            print(f"Selected latest endpoint version {latest_version}")

        self._api_url += f"{latest_version}/"
        self.version = Version.coerce(self.get_api_version())

    def _load_cookies(
            self, remote: str, username: Optional[str], password: Optional[str]
    ) -> None:
        if self._firewall == "F5":
            import requests

            cookies_file = f"{remote}-cookies.pkl"
            cookies_path = Path(appdirs.user_config_dir("simdb")) / cookies_file
            parsed_url = urlparse(self._url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

            cookies = None
            if os.path.exists(cookies_path):
                with open(cookies_path, "rb") as f:
                    cookies = pickle.load(f)
                r = requests.get(f"{self._url}/", cookies=cookies)
                try:
                    # check to see if the cookies are still valid by trying a simple request
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
                with requests.Session() as s:
                    s.get(base_url)
                    payload = {
                        "username": username,
                        "password": password,
                        "vhost": "standard",
                    }
                    p = s.post(f"{base_url}/my.policy", data=payload)
                    if p.status_code != 200:
                        raise RuntimeError(
                            "Failed to get firewall authentication cookies"
                        )
                    cookies = s.cookies

                os.umask(0)
                descriptor = os.open(
                    path=cookies_path,
                    flags=os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                    mode=0o600,
                )
                with open(descriptor, "wb") as f:
                    pickle.dump(cookies, f)

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

    def _get_auth(self) -> Union["AuthBase", Tuple]:
        from requests.auth import AuthBase

        class JWTAuth(AuthBase):
            def __init__(self, token):
                self._token = token

            def __call__(self, request: "requests.PreparedRequest"):
                request.headers["Authorization"] = f"JWT-Token {self._token}"
                return request

        if self._use_token:
            return JWTAuth(self._token)
        else:
            return self._username, self._password

    def get(
            self,
            url: str,
            params: Optional[Dict] = None,
            headers: Optional[Dict] = None,
            authenticate: Optional[bool] = True,
    ) -> "requests.Response":
        """
        Perform an HTTP GET request.

        @param url: the URL of the request.
        @param params: any additional parameters to send along with the request.
        @param headers: additional headers to send with the request.
        @param authenticate: True if we should send authentication headers with the request.
        @return:
        """
        import requests

        params = params if params is not None else {}
        headers = headers if headers is not None else {}
        headers["Accept-encoding"] = "gzip"

        if authenticate and self._server_auth != "None":
            res = requests.get(
                self._api_url + url,
                params=params,
                auth=self._get_auth(),
                headers=headers,
                cookies=self._cookies,
            )
        else:
            res = requests.get(
                self._api_url + url,
                params=params,
                headers=headers,
                cookies=self._cookies,
            )

        check_return(res)
        return res

    def put(self, url: str, data: Dict, **kwargs) -> "requests.Response":
        """
        Perform an HTTP PUT request.

        @param url: the URL of the request.
        @param data: the PUT data to send.
        @param kwargs: any additional keyword arguments to add to the request.
        @return:
        """
        import requests

        headers = {"Content-type": "application/json"}

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

    def post(self, url: str, data: Dict, **kwargs) -> "requests.Response":
        """
        Perform an HTTP POST request.

        @param url: the URL of the request.
        @param data: the POST data to send.
        @param kwargs: any additional keyword arguments to add to the request.
        @return:
        """
        import requests

        if "files" in kwargs:
            if data:
                raise Exception("Cannot send JSON data at the same time as files.")
            headers = {}
        else:
            headers = {"Content-type": "application/json"}
        post_data = json.dumps(data, cls=CustomEncoder, indent=2) if data else {}

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

    def patch(self, url: str, data: Dict, **kwargs) -> "requests.Response":
        """
        Perform an HTTP PATCH request.

        @param url: the URL of the request.
        @param data: the PATCH data to send.
        @param kwargs: any additional keyword arguments to add to the request.
        @return:
        """
        import requests

        headers = {"Content-type": "application/json"}

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

    def delete(self, url: str, data: Dict[Any, Any], **kwargs) -> "requests.Response":
        """
        Perform an HTTP DELETE request.

        @param url: the URL of the request.
        @param data: the DELETE data to send.
        @param kwargs: any additional keyword arguments to add to the request.
        @return:
        """
        import requests

        headers = {"Content-type": "application/json"}

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

    @try_request
    def get_token(self) -> str:
        res = self.get("token")
        data = res.json()
        return data["token"]

    @try_request
    def get_endpoints(self) -> List[str]:
        res = self.get("", authenticate=False)
        data = res.json()
        return data["endpoints"]

    @try_request
    def get_server_authentication(self) -> Optional[str]:
        res = self.get("", authenticate=False)
        data = res.json()
        return data.get("authentication")

    @try_request
    def get_api_version(self) -> str:
        res = self.get("", authenticate=False)
        data = res.json()
        return data["api_version"]

    @try_request
    def get_validation_schemas(self) -> List[Dict]:
        res = self.get("validation_schema")
        return res.json()

    @try_request
    def get_upload_options(self) -> List[Dict]:
        res = self.get("upload_options")
        return res.json()

    @try_request
    def list_simulations(
            self, meta: Optional[List[str]] = None, limit: int = 0
    ) -> List["Simulation"]:
        from ..database.models import Simulation

        args = "?" + "&".join(meta) if meta else ""
        headers = {"simdb-result-limit": str(limit)}
        res = self.get("simulations" + args, headers=headers)
        data = res.json(cls=CustomDecoder)
        return [Simulation.from_data(sim) for sim in data["results"]]

    @try_request
    def get_simulation(self, sim_id: str) -> "Simulation":
        from ..database.models import Simulation

        res = self.get("simulation/" + sim_id)
        return Simulation.from_data(res.json(cls=CustomDecoder))

    @try_request
    def trace_simulation(self, sim_id: str) -> dict:
        res = self.get("trace/" + sim_id)
        return res.json(cls=CustomDecoder)

    @try_request
    def query_simulations(
            self, constraints: List[str], meta: List[str], limit=0
    ) -> List["Simulation"]:
        from ..database.models import Simulation
        from ..remote import APIConstants

        params = {}
        for item in constraints:
            (key, value) = item.split("=")
            params[key] = value
        args = "?" + "&".join(meta) if meta else ""
        headers = {
            APIConstants.LIMIT_HEADER: str(limit),
            APIConstants.PAGE_HEADER: str(1),
        }
        res = self.get("simulations" + args, params, headers=headers)
        data = res.json(cls=CustomDecoder)
        return [Simulation.from_data(sim) for sim in data["results"]]

    @try_request
    def delete_simulation(self, sim_id: str) -> Dict:
        res = self.delete("simulation/" + sim_id, {})
        return res.json()

    @try_request
    def update_simulation(self, sim_id: str, update_type: "Simulation.Status") -> None:
        self.patch("simulation/" + sim_id, {"status": update_type.value})

    @try_request
    def validate_simulation(self, sim_id: str) -> Tuple[bool, str]:
        res = self.post("validate/" + sim_id, {})
        data = res.json()
        if data["passed"]:
            return True, ""
        else:
            return False, data["error"]

    @try_request
    def add_watcher(
            self, sim_id: str, user: str, email: str, notification: "Watcher.Notification"
    ) -> None:
        self.post(
            "watchers/" + sim_id,
            {"user": user, "email": email, "notification": notification.name},
        )

    @try_request
    def remove_watcher(self, sim_id: str, user: str) -> None:
        self.delete("watchers/" + sim_id, {"user": user})

    @try_request
    def list_watchers(self, sim_id: str) -> List[Tuple]:
        res = self.get("watchers/" + sim_id)
        return [(d["username"], d["email"], d["notification"]) for d in res.json()]

    @try_request
    def set_metadata(
            self, sim_id: str, key: str, value: Union[str, uuid.UUID, int, float]
    ) -> List[str]:
        res = self.patch("simulation/metadata/" + sim_id, {"key": key, "value": value})
        return [data["value"] for data in res.json()]

    @try_request
    def delete_metadata(self, sim_id: str, key: str) -> List[str]:
        res = self.delete("simulation/metadata/" + sim_id, {"key": key})
        return [data["value"] for data in res.json()]

    @try_request
    def get_directory(self) -> str:
        res = self.get("staging_dir")
        return res.json()["staging_dir"]

    def _push_file(
            self,
            path: Path,
            uuid: uuid.UUID,
            file_type: str,
            sim_data: Dict,
            chunk_size: int,
            out_stream: IO,
    ):
        print(f"Uploading file {path} ", file=out_stream, end="")
        num_chunks = 0
        for chunk_index, chunk in enumerate(
                _read_bytes_in_chunks(path, compressed=True, chunk_size=chunk_size)
        ):
            print(".", file=out_stream, end="", flush=True)
            self._send_chunk(chunk_index, chunk, chunk_size, uuid, file_type, sim_data)
            num_chunks += 1
        if num_chunks == 0:
            # empty file
            self._send_chunk(0, b"", chunk_size, uuid, file_type, sim_data)
        self.post(
            "files",
            data={
                "simulation": sim_data,
                "files": [
                    {
                        "chunks": num_chunks,
                        "file_type": file_type,
                        "file_uuid": uuid.hex,
                    }
                ],
            },
        )
        print("Complete".rjust(os.get_terminal_size()[0]-len(f"{from_path}")-16), file=out_stream, flush=True)

    def _send_chunk(
            self,
            chunk_index: int,
            chunk: bytes,
            chunk_size: int,
            uuid: uuid.UUID,
            file_type: str,
            sim_data: dict,
    ):
        data = {
            "simulation": sim_data,
            "file_type": file_type,
            "chunk_info": {uuid.hex: {"chunk_size": chunk_size, "chunk": chunk_index}},
        }
        files: List[Tuple[str, Tuple[str, bytes, str]]] = [
            (
                "data",
                (
                    "data",
                    json.dumps(data, cls=CustomEncoder).encode(),
                    "text/json",
                ),
            ),
            ("files", (uuid.hex, chunk, "application/octet-stream")),
        ]
        self.post("files", data={}, files=files)

    @try_request
    def push_simulation(
            self,
            simulation: "Simulation",
            out_stream: IO[str] = sys.stdout,
            add_watcher: bool = True,
    ) -> None:
        """
        Push the local simulation to the remote server.

        First we upload any files associated with the simulation, then push the simulation metadata.

        :param simulation: The Simulation to push to remote server
        :param out_stream: The IO stream to write messages to the user (default: stdout)
        :param add_watcher: Add the current user as a watcher of the simulation on the remote server
        """
        from ..validation import Validator, ValidationError
        from ..imas.utils import imas_files

        schemas = self.get_validation_schemas()
        try:
            for schema in schemas:
                Validator(schema).validate(simulation)
        except ValidationError as err:
            print("Warning: simulation does not validate.")
            print(f"Validation error: {err}.")

        options: Dict[str, bool] = {}
        try:
            options = self.get_upload_options()
        except FailedConnection:
            pass

        sim_data = simulation.data(recurse=True)

        if options.get("copy_files", True):
            chunk_size = 10 * 1024 * 1024  # 10 MB

            copy_ids = options.get("copy_ids", True)

            for file in simulation.inputs:
                if file.type == DataObject.Type.IMAS:
                    if not copy_ids:
                        print(f"Skipping IDS data {file}", file=out_stream, flush=True)
                        continue
                    for path in imas_files(file.uri):
                        sim_file = next(
                            (f for f in sim_data["inputs"] if f["uuid"] == file.uuid)
                        )
                        sim_file["uri"] = f"file:{path}"
                        self._push_file(
                            path, file.uuid, "input", sim_data, chunk_size, out_stream
                        )
                else:
                    self._push_file(
                        file.uri.path,
                        file.uuid,
                        "input",
                        sim_data,
                        chunk_size,
                        out_stream,
                    )

            for file in simulation.outputs:
                if file.type == DataObject.Type.IMAS:
                    if not copy_ids:
                        print(f"Skipping IDS data {file}", file=out_stream, flush=True)
                        continue
                    for path in imas_files(file.uri):
                        sim_file = next(
                            (f for f in sim_data["outputs"] if f["uuid"] == file.uuid)
                        )
                        sim_file["uri"] = f"file:{path}"
                        self._push_file(
                            path, file.uuid, "output", sim_data, chunk_size, out_stream
                        )
                else:
                    self._push_file(
                        file.uri.path,
                        file.uuid,
                        "output",
                        sim_data,
                        chunk_size,
                        out_stream,
                    )

        sim_data = simulation.data(recurse=True)

        print("Uploading simulation data ... ", file=out_stream, end="", flush=True)
        self.post(
            "simulations", data={"simulation": sim_data, "add_watcher": add_watcher}
        )
        print("Success", file=out_stream, flush=True)

    def _get_file_info(self, uuid: uuid.UUID) -> List[Tuple[Path, str]]:
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
        print(f"Downloading file {from_path}", file=out_stream, end="")
        r = self.get(f"file/download/{uuid.hex}/{index}")
        bytes = r.content
        os.makedirs(to_path.parent, exist_ok=True)
        sha1 = hashlib.sha1()
        sha1.update(bytes)
        if sha1.hexdigest() != checksum:
            raise APIError(f"Checksum failed for file {from_path}")
        open(to_path, "wb").write(bytes)
        print("Complete".rjust(os.get_terminal_size()[0]-len(f"{from_path}")-18), file=out_stream, flush=True)

    @try_request
    def pull_simulation(
            self, sim_id: str, directory: Path, out_stream: IO[str] = sys.stdout
    ) -> "Simulation":
        from ..uri import URI

        """
        Pull the simulation from the remote server.

        This involves downloading all the files associated with the simulation into the provided simulation directory.

        :param sim_id: The id of the Simulation to pull
        :param directory: The local directory to use as the root directory of the simulation
        :param out_stream: The IO stream to write messages to the user (default: stdout)
        """
        simulation = self.get_simulation(sim_id)
        if simulation is None:
            raise RemoteError(f"Failed to find simulation: {sim_id}")

        files = itertools.chain(simulation.inputs, simulation.outputs)

        for file in files:
            info = self._get_file_info(file.uuid)
            paths = [path for (path, _) in info]

            common_root = os.path.commonpath(paths)

            for index, (path, checksum) in enumerate(info):
                rel_path = directory / path.relative_to(common_root)
                self._pull_file(file.uuid, index, checksum, path, rel_path, out_stream)
                file.uri = URI(file.uri, path=path)

        return simulation

    @try_request
    def reset_database(self) -> None:
        self.post("reset", {})
