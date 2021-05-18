import os
import json
from typing import List, Dict, Callable, Tuple, IO, Iterable, Optional, Union, Any, TYPE_CHECKING
import gzip
import io
import sys
import click
import base64

from .manifest import DataObject
from ..config import Config

if TYPE_CHECKING or 'sphinx' in sys.modules:
    # Only importing these for type checking and documentation generation in order to speed up runtime startup.
    from simdb.database.models import Simulation, Watcher, File
    import requests
    from requests.auth import AuthBase


def numpy_hook(obj: Dict) -> Any:
    import numpy as np
    if 'type' in obj and obj['type'] == 'numpy.ndarray':
        bytes = base64.decodebytes(obj['bytes'].encode())
        return np.frombuffer(bytes, dtype=obj['dtype'])
    return obj


class NumpyDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        kwargs['object_hook'] = numpy_hook
        super().__init__(*args, **kwargs)


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        import numpy as np
        if isinstance(obj, np.ndarray):
            bytes = base64.b64encode(obj).decode()
            return {'type': 'numpy.ndarray', 'dtype': obj.dtype.name, 'bytes': bytes}
        return json.JSONEncoder.default(self, obj)


class FailedConnection(RuntimeError):
    pass


def try_request(func: Callable) -> Callable:
    def wrapped_func(*args, **kwargs):
        import requests
        try:
            return func(*args, **kwargs)
        except requests.ConnectionError as ex:
            raise FailedConnection(f"Connection failed to {ex.request.url}.")
    return wrapped_func


def read_bytes(path: str, compressed: bool=True) -> bytes:
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


def read_bytes_in_chunks(path: str, compressed: bool=True, chunk_size: int=1024) -> Iterable[bytes]:
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
            raise RuntimeError(data["error"])
        else:
            res.raise_for_status()


class RemoteAPI:
    # dir_path = os.path.dirname(os.path.realpath(__file__))
    # cert_path = os.path.join(dir_path, "../remote/server.crt")

    _remote: str

    def __init__(self, remote: Optional[str], username: Optional[str], password: Optional[str], config: Config) -> None:
        self._config: Config = config
        if not remote:
            remote = config.default_remote
        if not remote:
            raise KeyError('Remote name not provided and no default remote found in config.')
        self._remote = remote
        self._url: str = config.get_option(f'remote.{remote}.url')
        self._api_url: str = f'{self._url}/api/v{config.api_version}/'

        self._token = config.get_option(f'remote.{remote}.token', default='')
        if not self._token:
            if not username:
                username = config.get_option(f'remote.{remote}.username', default='')
                if not username:
                    username = click.prompt('Username', default=os.environ.get('USER', ''))
            if not password:
                password = click.prompt(f'Password for user {username}', hide_input=True)
        self._username = username
        self._password = password

        self.get_api_version()

    @property
    def remote(self) -> str:
        return self._remote

    def _get_auth(self) -> Union["AuthBase", Tuple]:
        from requests.auth import AuthBase

        class JWTAuth(AuthBase):
            def __init__(self, token):
                self._token = token

            def __call__(self, request: "requests.Request"):
                request.headers['Authorization'] = f'JWT-Token {self._token}'
                return request

        if self._token:
            return JWTAuth(self._token)
        else:
            return self._username, self._password

    def get(self, url: str, params: Dict=None) -> "requests.Response":
        import requests
        if params is None:
            params = {}
        res = requests.get(self._api_url + url, params=params, auth=self._get_auth())
        check_return(res)
        return res

    def put(self, url: str, data: Dict, **kwargs) -> "requests.Response":
        import requests
        headers = {'Content-type': 'application/json'}
        res = requests.put(self._api_url + url, data=json.dumps(data, cls=NumpyEncoder), headers=headers,
                           auth=self._get_auth(), **kwargs)
        check_return(res)
        return res

    def post(self, url: str, data: Dict, **kwargs) -> "requests.Response":
        import requests
        headers = {'Content-type': 'application/json'}
        res = requests.post(self._api_url + url, data=json.dumps(data, cls=NumpyEncoder), headers=headers,
                            auth=self._get_auth(), **kwargs)
        check_return(res)
        return res

    def patch(self, url: str, data: Dict, **kwargs) -> "requests.Response":
        import requests
        headers = {'Content-type': 'application/json'}
        res = requests.patch(self._api_url + url, data=json.dumps(data, cls=NumpyEncoder), headers=headers,
                             auth=self._get_auth(), **kwargs)
        check_return(res)
        return res

    def delete(self, url: str, data: Dict, **kwargs) -> "requests.Response":
        import requests
        headers = {'Content-type': 'application/json'}
        res = requests.delete(self._api_url + url, data=json.dumps(data, cls=NumpyEncoder), headers=headers,
                              auth=self._get_auth(), **kwargs)
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
    def get_api_version(self) -> int:
        res = self.get("")
        data = res.json()
        return data["version"]

    @try_request
    def get_validation_schema(self) -> Dict:
        res = self.get("validation_schema")
        return res.json()

    @try_request
    def list_simulations(self, meta: List[str]=None) -> List["Simulation"]:
        from ..database.models import Simulation
        args = '?' + '&'.join(meta) if meta else ''
        res = self.get("simulations" + args)
        return [Simulation.from_data(sim) for sim in res.json(cls=NumpyDecoder)]

    @try_request
    def get_simulation(self, sim_id: str) -> "Simulation":
        from ..database.models import Simulation
        res = self.get("simulation/" + sim_id)
        return Simulation.from_data(res.json(cls=NumpyDecoder))

    @try_request
    def query_simulations(self, constraints: List[str]) -> List["Simulation"]:
        from ..database.models import Simulation
        params = {}
        for item in constraints:
            (key, value) = item.split('=')
            params[key] = value

        res = self.get("simulations", params)
        return [Simulation.from_data(sim) for sim in res.json(cls=NumpyDecoder)]

    @try_request
    def delete_simulation(self, sim_id: str) -> Dict:
        res = self.delete("simulation/" + sim_id, {})
        return res.json()

    @try_request
    def update_simulation(self, sim_id: str, update_type: "Simulation.Status") -> None:
        self.patch("simulation/" + sim_id, {'status': update_type.value})

    @try_request
    def validate_simulation(self, sim_id: str) -> Tuple[bool, str]:
        res = self.post("validate/" + sim_id, {})
        data = res.json()
        if data['passed']:
            return True, ''
        else:
            return False, data['error']

    @try_request
    def add_watcher(self, sim_id: str, user: str, email: str, notification: "Watcher.Notification") -> None:
        self.post("watchers/" + sim_id, {'user': user, 'email': email, 'notification': notification.name})

    @try_request
    def remove_watcher(self, sim_id: str, user: str) -> None:
        self.delete("watchers/" + sim_id, {'user': user})

    @try_request
    def list_watchers(self, sim_id: str) -> List[Tuple]:
        res = self.get("watchers/" + sim_id)
        return [(d["username"], d["email"], d["notification"]) for d in res.json()]

    def _push_file(self, file: "File", file_type: str, sim_data: Dict, chunk_size: int, out_stream: IO):
        if file.type == DataObject.Type.FILE:
            path = file.uri.path
            print('Uploading file {} '.format(path), file=out_stream, end='')
            num_chunks = 0
            for i, chunk in enumerate(read_bytes_in_chunks(path, compressed=True, chunk_size=chunk_size)):
                print('.', file=out_stream, end='', flush=True)
                data = {
                    'simulation': sim_data,
                    'file_type': file_type,
                    'chunk_info': {file.uuid.hex: {'chunk_size': chunk_size, 'chunk': i}}
                }
                files: List[Tuple[str, Tuple[str, bytes, str]]] = [
                    ("data", ("data", json.dumps(data).encode(), "text/json")),
                    ("files", (file.uuid.hex, chunk, "application/octet-stream"))
                ]
                self.post("files", data={}, files=files)
                num_chunks += 1
            self.post("files", data={
                'simulation': sim_data,
                'files': [{'chunks': num_chunks, 'file_type': file_type, 'file_uuid': file.uuid.hex}]
            })
            print('Complete', file=out_stream, flush=True)
        elif file.type == DataObject.Type.IMAS:
            from uri import URI
            from ..imas.utils import copy_imas
            res = self.get("staging_dir/{}".format(sim_data['uuid']))
            data = res.json()
            out_uri = URI(file.uri)
            out_uri.query.remove('user')
            out_uri['path'] = data['staging_dir']
            print('Uploading IDS {} to {} ... '.format(file.uri, out_uri), file=out_stream, end='', flush=True)
            copy_imas(file.uri, out_uri)
            print('success', file=out_stream, flush=True)
            files = sim_data['outputs'] if file_type == 'output' else sim_data['inputs']
            file_data = next((f for f in files if f['uuid'] == file.uuid.hex), None)
            if file_data:
                file_data['uri'] = str(out_uri)
            else:
                raise Exception('Failed to find file in simulation')
            try:
                self.post("files", data={
                    'simulation': sim_data,
                    'files': [{'file_type': file_type, 'file_uuid': file.uuid.hex}]
                })
            except:
                # While IMAS requires a local file copy we need to remove it if the remote validation fails.
                shutil.rmtree(data['staging_dir']) 
                raise

    @try_request
    def push_simulation(self, simulation: "Simulation", out_stream: IO=sys.stdout) -> None:
        """
        Push the local simulation to the remote server.

        First we upload any files associated with the simulation, then push the simulation metadata.

        :param simulation: Simulation to push to remote server
        :param out_stream: IO stream to write messages to the user (default: stdout)
        """
        from ..validation import Validator, ValidationError

        schema = self.get_validation_schema()
        try:
            Validator(schema).validate(simulation)
        except ValidationError as err:
            print("Warning: simulation does not validate.")
            print(f"Validation error: {err}.")

        sim_data = simulation.data(recurse=True)
        chunk_size = 10*1024*1024  # 10 MB

        for file in simulation.inputs:
            self._push_file(file, 'input', sim_data, chunk_size, out_stream)

        for file in simulation.outputs:
            self._push_file(file, 'output', sim_data, chunk_size, out_stream)

        print('Uploading simulation data ... ', file=out_stream, end='', flush=True)
        self.post("simulations", data={'simulation': sim_data})
        print('Success', file=out_stream, flush=True)

    @try_request
    def reset_database(self) -> None:
        self.post("reset", {})
