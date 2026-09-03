import functools
import getpass
import gzip
import hashlib
import io
import itertools
import json
import os
import pickle
import shutil
import sys
import time
import uuid
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)
from urllib.parse import quote, urlparse

import appdirs
import click
import requests
from netCDF4 import Dataset
from requests.auth import AuthBase
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from semantic_version import Version

from simdb.checksum import CHECKSUM_ALGORITHM, READ_CHUNK_SIZE, hash_file
from simdb.cli.resumable_upload import resumable_upload
from simdb.config import Config
from simdb.database.models import Simulation
from simdb.enums import IngestionStatus
from simdb.imas.utils import SimDBUrl, imas_backend_for_directory, imas_files
from simdb.json import CustomDecoder, CustomEncoder
from simdb.remote import CLIENT_API_VERSIONS, APIConstants
from simdb.remote.models import FileData, SimulationPostData

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


def try_request(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.ConnectionError as ex:
            url = ex.request.url if ex.request is not None else "undefined"
            raise FailedConnection(
                f"""\
Connection failed to {url}

Please check that the URL is valid and that REQUESTS_CA_BUNDLE is set if required.
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


def versioned_method(*versions: str) -> Callable:
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

    def decorator(default: Callable) -> Callable:
        default_name = getattr(default, "__name__", repr(default))
        registry: Dict[str, Callable] = dict.fromkeys(versions, default)

        @functools.wraps(default)
        def wrapper(self, *args, **kwargs):
            selected = getattr(self, "_api_version", None)
            if selected is None:
                return default(self, *args, **kwargs)
            impl = registry.get(selected)
            if impl is None:
                raise RemoteError(
                    f"'{default_name}' is not supported by the negotiated API "
                    f"version '{selected}'. It requires one of: "
                    f"{', '.join(sorted(registry))}."
                )
            return impl(self, *args, **kwargs)

        def register(*impl_versions: str) -> Callable:
            def do_register(func: Callable) -> Callable:
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


def read_bytes(path: Path, compressed: bool = True) -> bytes:
    if compressed:
        with io.BytesIO() as buffer:
            with gzip.GzipFile(fileobj=buffer, mode="wb") as gz_file, path.open(
                "rb"
            ) as file_in:
                gz_file.write(file_in.read())
            # gz_file is now closed (gzip footer written); buffer is still open
            buffer.seek(0)
            return buffer.read()
    else:
        with path.open("rb") as file:
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


def select_api_version(
    server_versions: Iterable[str],
    client_versions: Iterable[str] = CLIENT_API_VERSIONS,
) -> Optional[str]:
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


def _check_file_is_imas(file: Path) -> bool:
    # NetCDF is identified by the IMAS "Conventions" attribute
    if file.suffix == ".nc":
        try:
            with Dataset(file, "r") as ds:
                if getattr(ds, "Conventions", None) == "IMAS":
                    return True
        except OSError:
            # Not a readable NetCDF file; fall back to the directory heuristics
            pass

    try:
        imas_backend_for_directory(file.parent)
    except ValueError:
        return False
    return True


def _partition_roots(config: Config) -> dict[str, str]:
    section = config.get_section("partition", default={})
    return {k: str(v) for k, v in section.items()}


def _find_partition_for_file(
    file: Path, partitions: Dict[str, str]
) -> Tuple[str, Path]:
    # Match the partition with the longest root so that a catch-all mapping
    # (e.g. "/") does not shadow more specific partitions.
    best: Optional[Tuple[str, Path]] = None
    best_depth = -1
    for partition, path in partitions.items():
        root = Path(path)
        try:
            relative = file.relative_to(root)
        except ValueError:
            continue
        depth = len(root.parts)
        if depth > best_depth:
            best = (partition, relative)
            best_depth = depth
    if best is None:
        raise APIError(
            f"File {file} is not located under any configured partition "
            f"(configured partitions: {', '.join(partitions) or 'none'})"
        )
    return best


def _file_data_for_partition(
    file: FileData, source: Path, partitions: Dict[str, str], keep_uuid: bool = True
) -> FileData:
    """Copy FILE with its URI rewritten relative to the partition holding SOURCE."""
    partition, partition_path = _find_partition_for_file(source, partitions)
    new_uri = SimDBUrl.build(scheme=partition, path=partition_path.as_posix())
    update: Dict[str, Any] = {
        "uri": new_uri.encoded_string(),
        "checksum": hash_file(source),
    }
    if not keep_uuid:
        update["uuid"] = uuid.uuid1()
    return file.model_copy(update=update)


def _source_files(file: FileData) -> List[Path]:
    """Return the local files that FILE refers to, expanding directories."""
    file_uri = SimDBUrl(file.uri)
    if file_uri.path is None:
        raise APIError(f"File URI has no path: {file.uri}")

    if file_uri.scheme == "imas":
        try:
            sources = sorted(imas_files(file_uri))
        except ValueError as err:
            raise APIError(f"Failed to list IMAS files of {file.uri}: {err}") from err
        if not sources:
            raise APIError(f"IMAS URI does not contain any files: {file.uri}")
        return sources

    file_path = Path(file_uri.path)
    if not file_path.is_dir():
        return [file_path]

    sources = []
    for sub_file in sorted(file_path.iterdir()):
        if sub_file.is_dir():
            raise APIError(f"Nested directory found in {file_path}: {sub_file.name}")
        sources.append(sub_file)
    return sources


def _expand_directories(
    files: Iterable[FileData], partitions: Dict[str, str]
) -> List[FileData]:
    new_file_list = []
    for file in files:
        sources = _source_files(file)
        keep_uuid = len(sources) == 1
        for source in sources:
            new_file_list.append(
                _file_data_for_partition(file, source, partitions, keep_uuid=keep_uuid)
            )
    return new_file_list


def _expand_directories_http(
    files: Iterable[FileData], sim_uuid: uuid.UUID
) -> List[Tuple[FileData, Path, str]]:
    """Expand directories / IMAS data into individual files for HTTP upload.

    Returns ``(file_data, local_source_path, target)`` triples. Structure
    handling (IMAS directories stay grouped, standalone files stay flat) is
    identical to local push, but unlike ``push_local`` the file bytes are
    uploaded, so partitions play no role: each file keeps its absolute local
    path, namespaced under ``<sim_uuid>/file/``, and is assigned an ``http://``
    URI so the server stages it into the ``http`` partition. The server's
    existing copy step strips the common root exactly as it does for local
    push.
    """
    result: List[Tuple[FileData, Path, str]] = []
    for file in files:
        file_uri = SimDBUrl(file.uri)
        if file_uri.path is None:
            raise ValueError("File has no associated path")
        file_path = Path(file_uri.path)
        if file_uri.scheme == "imas":
            qs = dict(file_uri.query_params())
            path = qs.get("path")
            if path is None:
                raise ValueError("IMAS uri has not path set")
            file_path = Path(path)

        if file_path.is_dir():
            for sub_file in file_path.iterdir():
                if sub_file.is_dir():
                    raise ValueError("Nested directory found")
                result.append(_make_http_entry(file, sub_file, sim_uuid))
        else:
            result.append(_make_http_entry(file, file_path, sim_uuid))
    return result


def _make_http_entry(
    template: FileData,
    local_path: Path,
    sim_uuid: uuid.UUID,
) -> Tuple[FileData, Path, str]:
    """Build the HTTP upload entry for a single local file.

    HTTP uploads carry the file bytes from the local system, so partitions are
    not consulted: the file's absolute path is namespaced under
    ``<sim_uuid>/file/``, which keeps targets unique on the server.

    The checksum is left empty here and filled in later by
    :func:`_compute_checksums`, so that hashing (a full read of every file) can be
    reported with a progress bar instead of stalling silently before the upload.
    """
    rel_posix = local_path.as_posix().lstrip("/")
    target = f"{sim_uuid.hex}/file/{rel_posix}"
    new_uri = SimDBUrl.build(scheme="http", path=target, host="")
    file_type = "IMAS" if _check_file_is_imas(local_path) else template.type
    return (
        FileData(
            type=file_type,
            uri=new_uri.encoded_string(),
            checksum="",
            datetime=template.datetime,
            usage=template.usage,
            purpose=template.purpose,
            sensitivity=template.sensitivity,
            access=template.access,
            embargo=template.embargo,
        ),
        local_path,
        target,
    )


def _compute_checksums(files: List[Tuple[FileData, Path, str]]) -> None:
    """Compute and store the SHA-1 checksum of each file, reporting progress.

    Hashing reads every file in full and is the main delay before the upload
    starts, so surface it with a byte-level progress bar (mirroring the upload
    bars). The computed checksum is stored as the catalog checksum.
    """
    total_bytes = sum(local_path.stat().st_size for _, local_path, _ in files)
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Calculating checksums", total=total_bytes)
        for file_data, local_path, _target in files:
            progress.update(task, description=f"Hashing {local_path.name}")
            file_data.checksum = hash_file(
                local_path, progress=lambda n: progress.advance(task, n)
            )
        progress.update(task, description="Calculated checksums")


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

        self._firewall: Optional[str] = config.get_string_option(
            f"remote.{remote}.firewall", default=None
        )

        if not username:
            username = config.get_string_option(f"remote.{remote}.username", default="")

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

        if username == "admin":
            self._server_auth = "admin-auth"

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

        selected_version = select_api_version(endpoint_versions)
        if selected_version is None:
            raise RemoteError(
                "No compatible API version found on remote: the server provides "
                f"{', '.join(endpoint_versions) or 'none'} and this client supports "
                f"{', '.join(CLIENT_API_VERSIONS)}."
            )

        if config.verbose:
            print(f"Selected API version {selected_version}")

        self._api_version = selected_version
        self._api_url += f"{selected_version}/"
        self.version = Version.coerce(self.get_api_version())
        self.server_version = Version.coerce(self.get_server_version())

    def _load_cookies(
        self, remote: str, username: Optional[str], password: Optional[str]
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

    def _get_auth(self) -> Union["AuthBase", Tuple]:
        class JWTAuth(AuthBase):
            def __init__(self, token):
                self._token = token

            def __call__(self, r):
                if r.headers is not None:
                    r.headers["Authorization"] = f"JWT-Token {self._token}"
                return r

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
        stream: Optional[bool] = False,
    ) -> "requests.Response":
        """
        Perform an HTTP GET request.

        :param url: the URL of the request.
        :param params: any additional parameters to send along with the request.
        :param headers: additional headers to send with the request.
        :param authenticate: True if we should send authentication headers with
            the request.
        :param stream: True to enable streaming.
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

    def put(self, url: str, data: Dict, **kwargs) -> "requests.Response":
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

    def post(self, url: str, data: Dict, **kwargs) -> "requests.Response":
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

    def patch(self, url: str, data: Dict, **kwargs) -> "requests.Response":
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

    def delete(self, url: str, data: Dict[Any, Any], **kwargs) -> "requests.Response":
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
    def get_endpoints(self) -> List[str]:
        res = self.get("", authenticate=False)
        data = res.json()
        return data["endpoints"]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_server_authentication(self) -> Optional[str]:
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
    def get_validation_schemas(self) -> List[Dict]:
        res = self.get("validation_schema")
        return res.json()

    @versioned_method("v1.2", "v1.3")
    @try_request
    def get_upload_options(self) -> Dict[str, Any]:
        try:
            res = self.get("upload_options")
            return res.json()
        except FailedConnection:
            # old remotes may not provide this endpoint
            return {}

    @versioned_method("v1.2", "v1.3")
    @try_request
    def list_simulations(
        self, meta: Optional[List[str]] = None, limit: int = 0
    ) -> List["Simulation"]:
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
        self, constraints: List[str], meta: List[str], limit=0
    ) -> List["Simulation"]:
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
    def delete_simulation(self, sim_id: str) -> Dict:
        res = self.delete("simulation/" + sim_id, {})
        return res.json()

    @versioned_method("v1.2", "v1.3")
    @try_request
    def update_simulation(self, sim_id: str, update_type: "Simulation.Status") -> None:
        self.patch("simulation/" + sim_id, {"status": update_type.value})

    @versioned_method("v1.2", "v1.3")
    @try_request
    def validate_simulation(self, sim_id: str) -> Tuple[bool, str]:
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
    def list_watchers(self, sim_id: str) -> List[Tuple]:
        res = self.get("watchers/" + sim_id)
        return [(d["username"], d["email"], d["notification"]) for d in res.json()]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def set_metadata(
        self, sim_id: str, key: str, value: Union[str, uuid.UUID, int, float]
    ) -> List[str]:
        res = self.patch("simulation/metadata/" + sim_id, {"key": key, "value": value})
        return [data["value"] for data in res.json()]

    @versioned_method("v1.2", "v1.3")
    @try_request
    def delete_metadata(self, sim_id: str, key: str) -> List[str]:
        res = self.delete("simulation/metadata/" + sim_id, {"key": key})
        return [data["value"] for data in res.json()]

    @versioned_method("v1.3")
    @try_request
    def get_simulation_data(
        self, sim_id: str, path: str, dd_version: Optional[str] = None
    ) -> Dict[str, Any]:
        params = {"path": path}
        if dd_version is not None:
            params["dd_version"] = dd_version
        res = self.get(f"simulation/{sim_id}/data", params=params)
        return res.json()

    @try_request
    def get_directory(self) -> str:
        res = self.get("staging_dir")
        return res.json()["staging_dir"]

    def _push_file(
        self,
        path: Path,
        uuid: uuid.UUID,
        file_type: str,
        sim_data: Dict[str, Any],
        chunk_size: int,
        type: DataType,
    ):
        msg = f"Uploading file {path} "
        print(msg, end="")
        num_chunks = 0
        for chunk_index, chunk in enumerate(
            _read_bytes_in_chunks(path, compressed=True, chunk_size=chunk_size)
        ):
            print(".", end="")
            self._send_chunk(chunk_index, chunk, chunk_size, uuid, file_type, sim_data)
            num_chunks += 1
        if num_chunks == 0:
            # empty file
            self._send_chunk(0, b"", chunk_size, uuid, file_type, sim_data)
        if type == DataType.FILE:
            self.post(
                "files",
                data={
                    "simulation": sim_data,
                    "obj_type": DataType.FILE,
                    "files": [
                        {
                            "chunks": num_chunks,
                            "file_type": file_type,
                            "file_uuid": uuid.hex,
                            "ids_list": None,
                        }
                    ],
                },
            )
        print(f"\r{msg}", end="")
        print(
            "Complete".rjust(shutil.get_terminal_size().columns - len(msg)),
        )

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

    @versioned_method("v1.3")
    @try_request
    def push_local_simulation(self, simulation: Simulation, add_watcher: bool = False):
        sim_data = simulation.to_model(recurse=True)

        partitions = _partition_roots(self._config)
        sim_data.inputs.root = _expand_directories(sim_data.inputs.root, partitions)
        sim_data.outputs.root = _expand_directories(sim_data.outputs.root, partitions)

        uploaded_by = simulation.meta_dict().get("uploaded_by")

        post_data = SimulationPostData(
            simulation=sim_data,
            add_watcher=add_watcher,
            uploaded_by=str(uploaded_by) if uploaded_by is not None else None,
        )
        self.post("simulations", data=post_data.model_dump(mode="json"))

    def _upload_files(
        self,
        files: List[Tuple[FileData, Path, str]],
        upload_headers: Dict[str, str],
    ):
        """Upload the expanded files over resumable HTTP, showing two progress
        bars: an overall bar across all bytes and a sub-bar for the current file.
        """
        total_bytes = sum(local_path.stat().st_size for _, local_path, _ in files)

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            overall = progress.add_task("Overall", total=total_bytes)
            file_task = progress.add_task("", total=0)
            uploaded = 0
            for _file_data, local_path, target in files:
                size = local_path.stat().st_size
                progress.reset(
                    file_task, total=size, description=f"  {local_path.name}"
                )
                url = f"{self._api_url}upload/{quote(target)}"

                def _on_progress(completed: int, _base: int = uploaded) -> None:
                    progress.update(file_task, completed=completed)
                    progress.update(overall, completed=_base + completed)

                resumable_upload(
                    url,
                    local_path,
                    auth=self._get_auth() if self._server_auth != "None" else None,
                    cookies=self._cookies,
                    headers=upload_headers,
                    progress=_on_progress,
                )
                uploaded += size
                progress.update(file_task, completed=size)
                progress.update(overall, completed=uploaded)

    @versioned_method("v1.3")
    @try_request
    def push_simulation(
        self,
        simulation: Simulation,
        add_watcher: bool = False,
    ):
        """Push a simulation by uploading its files over resumable HTTP.

        Unlike :meth:`push_local_simulation` (which requires a filesystem shared
        with the server), this uploads the file bytes to the server's ``http``
        partition using a resumable protocol, then pushes the metadata.
        """
        sim_data = simulation.to_model(recurse=True)

        inputs = _expand_directories_http(sim_data.inputs.root, simulation.uuid)
        outputs = _expand_directories_http(sim_data.outputs.root, simulation.uuid)

        files = list(itertools.chain(inputs, outputs))
        upload_headers = {"User-Agent": "it_script_basic"}
        if files:
            _compute_checksums(files)
            self._upload_files(files, upload_headers)

        sim_data.inputs.root = [file_data for file_data, _, _ in inputs]
        sim_data.outputs.root = [file_data for file_data, _, _ in outputs]

        uploaded_by = simulation.meta_dict().get("uploaded_by")

        post_data = SimulationPostData(
            simulation=sim_data,
            add_watcher=add_watcher,
            uploaded_by=str(uploaded_by) if uploaded_by is not None else None,
        )
        self.post("simulations", data=post_data.model_dump(mode="json"))

        print("Waiting for ingestion to complete...", end="")
        last_status = None
        while True:
            try:
                status = self.get_ingestion_status(simulation.uuid.hex)
            except Exception as err:
                raise APIError(f"Failed to check ingestion status: {err}") from err

            if status != last_status:
                if last_status is not None:
                    print(f" -> {status.value}", end="")
                else:
                    print(f" {status.value}", end="")
                last_status = status

            if status.is_terminal():
                break

            time.sleep(1)

        if status == IngestionStatus.COMPLETED:
            return
        else:
            raise APIError(f"Simulation ingestion failed with status: {status.value}")

    @versioned_method("v1.3")
    @try_request
    def get_ingestion_status(self, sim_id: str) -> IngestionStatus:
        res = self.get(f"simulation/status/{sim_id}")
        return IngestionStatus(res.json()["status"])

    @push_simulation.register("v1.2")
    @try_request
    def _push_simulation_v12(
        self,
        simulation: "Simulation",
        add_watcher: bool = True,
    ) -> None:
        """
        Push the local simulation to the remote server.

        First we upload any files associated with the simulation, then push the
        simulation metadata.

        :param simulation: The Simulation to push to remote server
        :param add_watcher: Add the current user as a watcher of the simulation on the
                            remote server
        """

        sim_data = simulation.data(recurse=True)

        try:
            sim_json = json.dumps(
                sim_data, cls=CustomEncoder, separators=(",", ":")
            ).encode("utf-8")
            sim_json_size = len(sim_json)
        except Exception:
            sim_json_size = 0

        # Target max request (10MB minus headroom); adjust chunk size so
        # (chunk + sim_data JSON) fits
        MAX_REQUEST_BYTES = 9 * 1024 * 1024  # nominal 10 MB limit
        HEADROOM = 2048  # for JSON envelope & headers
        # Base chunk size before adjustment (previous constant)
        base_chunk_size = 8 * 1024 * 1024
        # Compute allowed chunk payload
        allowed_chunk = max(
            1024, min(base_chunk_size, MAX_REQUEST_BYTES - sim_json_size - HEADROOM)
        )

        options = self.get_upload_options()
        if options.get("copy_files", True):
            chunk_size = allowed_chunk  # 10 MB limit on ITER network

            copy_ids = options.get("copy_ids", True)

            for file in simulation.inputs:
                if file.type == DataType.IMAS:
                    if not copy_ids:
                        print(f"Skipping IDS data {file}")
                        continue
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
                            f for f in sim_data["inputs"] if f.get("uuid") == file.uuid
                        )
                        sim_file["uri"] = f"file:{path}"
                        self._push_file(
                            path,
                            file.uuid,
                            "input",
                            sim_data,
                            chunk_size,
                            file.type,
                        )

                    self.post(
                        "files",
                        data={
                            "simulation": simulation.data(recurse=True),
                            "obj_type": file.type,
                            "files": [
                                {
                                    "file_type": "input",
                                    "file_uuid": file.uuid.hex,
                                    "ids_list": ids_list,
                                }
                            ],
                        },
                    )

                else:
                    if file.uri and file.uri.path:
                        self._push_file(
                            Path(file.uri.path),
                            file.uuid,
                            "input",
                            sim_data,
                            chunk_size,
                            file.type,
                        )

            for file in simulation.outputs:
                if file.type == DataType.IMAS:
                    if not copy_ids:
                        print(f"Skipping IDS data {file}")
                        continue

                    ids_list = simulation.meta_dict().get("ids", [])
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
                            (
                                f
                                for f in sim_data["outputs"]
                                if f.get("uuid") == file.uuid
                            ),
                            None,
                        )
                        if sim_file:
                            sim_file["uri"] = f"file:{path}"
                        self._push_file(
                            path,
                            file.uuid,
                            "output",
                            sim_data,
                            chunk_size,
                            file.type,
                        )

                    self.post(
                        "files",
                        data={
                            "simulation": simulation.data(recurse=True),
                            "obj_type": file.type,
                            "files": [
                                {
                                    "file_type": "output",
                                    "file_uuid": file.uuid.hex,
                                    "ids_list": ids_list,
                                }
                            ],
                        },
                    )
                else:
                    if file.uri and file.uri.path:
                        self._push_file(
                            Path(file.uri.path),
                            file.uuid,
                            "output",
                            sim_data,
                            chunk_size,
                            file.type,
                        )

        sim_data = simulation.data(recurse=True)
        uploaded_by = simulation.meta_dict().get("uploaded_by", None)
        print("Uploading simulation data ... ", end="")
        self.post(
            "simulations",
            data={
                "simulation": sim_data,
                "add_watcher": add_watcher,
                "uploaded_by": uploaded_by,
            },
        )
        print("Success")

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
        msg = f"Downloading file {from_path} to {to_path}"
        print(
            msg,
            file=out_stream,
            flush=True,
        )
        response = self.get(f"file/download/{uuid.hex}/{index}", stream=True)

        to_path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.new(CHECKSUM_ALGORITHM)

        with to_path.open("wb") as f:
            total_length = response.headers.get("content-length")
            if total_length is None:
                f.write(response.content)
            else:
                downloaded = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=READ_CHUNK_SIZE):
                    digest.update(data)
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

        if digest.hexdigest() != checksum:
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
