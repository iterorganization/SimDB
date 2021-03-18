import os
import requests
import json
from typing import List, Dict, Callable, Tuple, IO, Iterable
import gzip
import io
import urllib3
import sys
from uri import URI

from ..database.models import Simulation, File
from .manifest import DataObject
from ..config import Config
from ..validation import Validator, ValidationError


urllib3.disable_warnings()


class FailedConnection(RuntimeError):
    pass


def try_request(func: Callable) -> Callable:
    def wrapped_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.ConnectionError:
            raise FailedConnection("Failed to connect to remote API")
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


def check_return(res: requests.Response) -> None:
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
    dir_path = os.path.dirname(os.path.realpath(__file__))
    cert_path = os.path.join(dir_path, "../remote/server.crt")

    def __init__(self, name: str, config: Config) -> None:
        self._config: Config = config
        self._url: str = config.get_option('remote.%s.url' % name)
        if not self._url:
            raise ValueError("cannot find remote %s" % name)
        self._api_url: str = '%s/api/v%s/' % (self._url, config.api_version)
        self._user_name: str = config.get_option('user.name', default='test')
        self._pass_word: str = config.get_option('user.password', default='test')

    def get(self, url: str, params: Dict=None) -> requests.Response:
        if params is None:
            params = {}
        res = requests.get(self._api_url + url, params=params, auth=(self._user_name, self._pass_word))
        # res = requests.get(self.url + url, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        check_return(res)
        return res

    def put(self, url: str, data: Dict, **kwargs) -> requests.Response:
        # res = requests.put(self.url + url, json=data, auth=(self.user_name, self.pass_word), verify=self.cert_path, **kwargs)
        res = requests.put(self._api_url + url, json=data, auth=(self._user_name, self._pass_word), **kwargs)
        check_return(res)
        return res

    def post(self, url: str, data: Dict, **kwargs) -> requests.Response:
        # res = requests.post(self.url + url, json=data, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        res = requests.post(self._api_url + url, json=data, auth=(self._user_name, self._pass_word), **kwargs)
        check_return(res)
        return res

    def delete(self, url: str, data: Dict) -> requests.Response:
        # res = requests.delete(self.url + url, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        res = requests.delete(self._api_url + url, json=data, auth=(self._user_name, self._pass_word))
        check_return(res)
        return res

    def has_url(self) -> bool:
        return bool(self._url)

    @try_request
    def get_validation_schema(self) -> Dict:
        res = self.get("validation_schema")
        return res.json()

    @try_request
    def list_simulations(self) -> List[Simulation]:
        res = self.get("simulations")
        return [Simulation.from_data(sim) for sim in res.json()]

    @try_request
    def get_simulation(self, sim_id: str) -> Simulation:
        res = self.get("simulation/" + sim_id)
        return Simulation.from_data(res.json())

    @try_request
    def query_simulations(self, constraints: List[str]) -> List[Simulation]:
        params = {}
        for item in constraints:
            (key, value) = item.split('=')
            params[key] = value

        res = self.get("simulations", params)
        return [Simulation.from_data(sim) for sim in res.json()]

    @try_request
    def delete_simulation(self, sim_id: str) -> Dict:
        res = self.delete("simulation/" + sim_id, {})
        return res.json()

    @try_request
    def publish_simulation(self, sim_id: str) -> None:
        self.post("publish/" + sim_id, {})

    @try_request
    def add_watcher(self, sim_id: str, user: str, email: str, notification: str) -> None:
        self.post("watchers/" + sim_id, {'user': user, 'email': email, 'notification': notification})

    @try_request
    def remove_watcher(self, sim_id: str, user: str) -> None:
        self.delete("watchers/" + sim_id, {'user': user})

    @try_request
    def list_watchers(self, sim_id: str) -> List[Tuple]:
        res = self.get("watchers/" + sim_id)
        return [(d["username"], d["email"]) for d in res.json()]

    def _push_file(self, file: File, file_type: str, sim_data: Dict, chunk_size: int, out_stream: IO):
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
            self.post("files", data={
                'simulation': sim_data,
                'files': [{'file_type': file_type, 'file_uuid': file.uuid.hex}]
            })

    @try_request
    def push_simulation(self, simulation: Simulation, out_stream: IO=sys.stdout) -> None:
        """
        Push the local simulation to the remote server.

        First we upload any files associated with the simulation, then push the simulation metadata.

        :param simulation: Simulation to push to remote server
        :param out_stream: IO stream to write messages to the user (default: stdout)
        """
        schema = self.get_validation_schema()
        try:
            Validator(schema).validate(simulation)
        except ValidationError as err:
            print("warning: simulation does not validate")
            print("validation error: ", err)

        sim_data = simulation.data(recurse=True)
        chunk_size = 10*1024*1024  # 10 MB

        for file in simulation.inputs:
            self._push_file(file, 'input', sim_data, chunk_size, out_stream)

        for file in simulation.outputs:
            self._push_file(file, 'output', sim_data, chunk_size, out_stream)

        print('Uploading simulation data ... ', file=out_stream, end='', flush=True)
        self.post("simulations", data={'simulation': sim_data})
        print('success', file=out_stream, flush=True)

    @try_request
    def reset_database(self) -> None:
        self.post("reset", {})
