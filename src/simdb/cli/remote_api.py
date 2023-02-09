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
)
import gzip
import io
import sys
import click
import itertools
import hashlib
from pathlib import Path
from semantic_version import Version

from .manifest import DataObject
from ..config import Config
from ..json import CustomDecoder, CustomEncoder


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
            raise FailedConnection(f"Connection failed to {ex.request.url}.")

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


def read_bytes_in_chunks(
    path: str, compressed: bool = True, chunk_size: int = 1024
) -> Iterable[bytes]:
    with open(path, "rb") as file_in:
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
            raise ValueError(f"Remote '{remote}' not found.")

        if use_token is not None:
            self._use_token = use_token
        else:
            self._use_token = not username and not password

        if not username:
            username = config.get_option(f"remote.{remote}.username", default="")

        if password and not username:
            raise ValueError(
                "Password given but no username given or found in configuration."
            )

        if not self._use_token:
            if not username:
                username = click.prompt("Username", default=os.environ.get("USER", ""))
            if not password:
                password = click.prompt(
                    f"Password for user {username}", hide_input=True
                )

        self._token = config.get_option(f"remote.{remote}.token", default="")
        if self._use_token and not self._token:
            raise ValueError("No username or password given and no token found.")

        self._username = username
        self._password = password

        self._api_url: str = f"{self._url}/"

        endpoints = self.get_endpoints()
        endpoint_versions = [endpoint.split("/")[-1] for endpoint in endpoints]

        if not endpoint_versions:
            raise RemoteError("No compatible API version found on remote")

        latest_version = max(endpoint_versions)
        if config.verbose:
            print(f"Selected latest endpoint version {latest_version}")

        self._api_url += f"{latest_version}/"
        self.version = Version.coerce(self.get_api_version())

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
        if authenticate:
            res = requests.get(
                self._api_url + url,
                params=params,
                auth=self._get_auth(),
                headers=headers,
            )
        else:
            res = requests.get(self._api_url + url, params=params, headers=headers)
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
        res = requests.put(
            self._api_url + url,
            data=json.dumps(data, cls=CustomEncoder),
            headers=headers,
            auth=self._get_auth(),
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
        res = requests.post(
            self._api_url + url,
            data=post_data,
            headers=headers,
            auth=self._get_auth(),
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
        res = requests.patch(
            self._api_url + url,
            data=json.dumps(data, cls=CustomEncoder),
            headers=headers,
            auth=self._get_auth(),
            **kwargs,
        )
        check_return(res)
        return res

    def delete(self, url: str, data: Dict, **kwargs) -> "requests.Response":
        """
        Perform an HTTP DELETE request.

        @param url: the URL of the request.
        @param data: the DELETE data to send.
        @param kwargs: any additional keyword arguments to add to the request.
        @return:
        """
        import requests

        headers = {"Content-type": "application/json"}
        res = requests.delete(
            self._api_url + url,
            data=json.dumps(data, cls=CustomEncoder),
            headers=headers,
            auth=self._get_auth(),
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
    def get_api_version(self) -> str:
        res = self.get("", authenticate=False)
        data = res.json()
        return data["api_version"]

    @try_request
    def get_validation_schemas(self) -> List[Dict]:
        res = self.get("validation_schema")
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
        from ..remote.apis.v1_1.simulations import SimulationList

        params = {}
        for item in constraints:
            (key, value) = item.split("=")
            params[key] = value
        args = "?" + "&".join(meta) if meta else ""
        headers = {
            SimulationList.LIMIT_HEADER: str(limit),
            SimulationList.PAGE_HEADER: str(1),
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
    def set_metadata(self, sim_id: str, key: str, value: Union[str, uuid.UUID, int, float]) -> List[str]:
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
        file: "File",
        file_type: str,
        sim_data: Dict,
        chunk_size: int,
        out_stream: IO,
    ):
        if file.type == DataObject.Type.FILE:
            path = file.uri.path
            print("Uploading file {} ".format(path), file=out_stream, end="")
            num_chunks = 0
            for i, chunk in enumerate(
                read_bytes_in_chunks(path, compressed=True, chunk_size=chunk_size)
            ):
                print(".", file=out_stream, end="", flush=True)
                self.send_chunk(i, chunk, chunk_size, file, file_type, sim_data)
                num_chunks += 1
            if num_chunks == 0:
                # empty file
                self.send_chunk(0, b"", chunk_size, file, file_type, sim_data)
            self.post(
                "files",
                data={
                    "simulation": sim_data,
                    "files": [
                        {
                            "chunks": num_chunks,
                            "file_type": file_type,
                            "file_uuid": file.uuid.hex,
                        }
                    ],
                },
            )
            print("Complete", file=out_stream, flush=True)
        elif file.type == DataObject.Type.IMAS:
            from ..uri import URI
            from ..imas.utils import copy_imas

            res = self.get("staging_dir/{}".format(sim_data["uuid"].hex))
            data = res.json()
            out_uri = URI(str(file.uri))
            if "user" in out_uri.query:
                out_uri.query.remove("user")
            path = Path(data["staging_dir"]) / file.uuid.hex
            out_uri.query.set("path", path)
            print(
                "Uploading IDS {}\n           to {} ... ".format(file.uri, out_uri),
                file=out_stream,
                end="",
                flush=True,
            )
            copy_imas(file.uri, out_uri)
            print("success", file=out_stream, flush=True)
            files = sim_data["outputs"] if file_type == "output" else sim_data["inputs"]
            file_data = next((f for f in files if f["uuid"] == file.uuid), None)
            if file_data:
                file_data["uri"] = str(out_uri)
            else:
                raise Exception("Failed to find file in simulation")
            try:
                self.post(
                    "files",
                    data={
                        "simulation": sim_data,
                        "files": [{"file_type": file_type, "file_uuid": file.uuid.hex}],
                    },
                )
            except Exception:
                import shutil

                # While IMAS requires a local file copy we need to remove it if the remote validation fails.
                shutil.rmtree(data["staging_dir"])
                raise

    def send_chunk(self, i, chunk, chunk_size, file, file_type, sim_data):
        data = {
            "simulation": sim_data,
            "file_type": file_type,
            "chunk_info": {file.uuid.hex: {"chunk_size": chunk_size, "chunk": i}},
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
            ("files", (file.uuid.hex, chunk, "application/octet-stream")),
        ]
        self.post("files", data={}, files=files)

    @try_request
    def push_simulation(
        self, simulation: "Simulation", out_stream: IO = sys.stdout
    ) -> None:
        """
        Push the local simulation to the remote server.

        First we upload any files associated with the simulation, then push the simulation metadata.

        :param simulation: The Simulation to push to remote server
        :param out_stream: The IO stream to write messages to the user (default: stdout)
        """
        from ..validation import Validator, ValidationError

        schemas = self.get_validation_schemas()
        try:
            for schema in schemas:
                Validator(schema).validate(simulation)
        except ValidationError as err:
            print("Warning: simulation does not validate.")
            print(f"Validation error: {err}.")

        sim_data = simulation.data(recurse=True)
        chunk_size = 10 * 1024 * 1024  # 10 MB

        for file in simulation.inputs:
            self._push_file(file, "input", sim_data, chunk_size, out_stream)

        for file in simulation.outputs:
            self._push_file(file, "output", sim_data, chunk_size, out_stream)

        print("Uploading simulation data ... ", file=out_stream, end="", flush=True)
        self.post("simulations", data={"simulation": sim_data})
        print("Success", file=out_stream, flush=True)

    def _pull_file(
        self,
        file: "File",
        path: Path,
        out_stream: IO,
    ):
        if file.type == DataObject.Type.FILE:
            print(f"Downloading file {file.uri.path} ", file=out_stream, end="")
            r = self.get(f"file/download/{file.uuid.hex}")
            bytes = r.content
            os.makedirs(path.parent, exist_ok=True)
            sha1 = hashlib.sha1()
            sha1.update(bytes)
            if sha1.hexdigest() != file.checksum:
                raise APIError(f"Checksum failed for file {file.uri.path}")
            open(path, "wb").write(bytes)
            print("Complete", file=out_stream, flush=True)
        elif file.type == DataObject.Type.IMAS:
            raise APIError("IMAS file types not yet supported for download")

    @try_request
    def pull_simulation(
        self, sim_id: str, directory: Path, out_stream: IO = sys.stdout
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

        common_root = os.path.commonpath(
            [f.uri.path for f in itertools.chain(simulation.inputs, simulation.outputs)]
        )

        for file in simulation.inputs:
            path = directory / file.uri.path.relative_to(common_root)
            self._pull_file(file, path, out_stream)
            file.uri = URI(file.uri, path=path)

        for file in simulation.outputs:
            path = directory / file.uri.path.relative_to(common_root)
            self._pull_file(file, path, out_stream)
            file.uri = URI(file.uri, path=path)

        return simulation

    @try_request
    def reset_database(self) -> None:
        self.post("reset", {})
