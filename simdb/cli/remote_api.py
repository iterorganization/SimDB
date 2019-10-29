import os
import requests
import json
from typing import List, Dict, Callable, Tuple
import gzip
import io
import urllib3

from ..database.models import Simulation
from .manifest import DataObject
from ..config.config import Config


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
            with gzip.GzipFile(fileobj=buffer, mode="wb") as gzfile:
                with open(path, "rb") as file_in:
                    gzfile.write(file_in.read())
            buffer.seek(0)
            return buffer.read()
    else:
        with open(path, "rb") as file:
            return file.read()


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

    def __init__(self, config: Config) -> None:
        self._config: Config = config
        self._api_url: str = '%s/api/v%s/' % (config.get_option('remote-url'), config.api_version)
        self._user_name: str = config.get_option('user-name', default='test')
        self._pass_word: str = config.get_option('user-password', default='test')

    def get(self, url: str, params: Dict = {}) -> requests.Response:
        res = requests.get(self._api_url + url, params=params, auth=(self._user_name, self._pass_word))
        #res = requests.get(self.url + url, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        check_return(res)
        return res

    def put(self, url: str, data: Dict, **kwargs) -> requests.Response:
        # res = requests.put(self.url + url, json=data, auth=(self.user_name, self.pass_word), verify=self.cert_path, **kwargs)
        res = requests.put(self._api_url + url, json=data, auth=(self._user_name, self._pass_word), **kwargs)
        check_return(res)
        return res

    def post(self, url: str, data: Dict) -> requests.Response:
        # res = requests.post(self.url + url, json=data, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        res = requests.post(self._api_url + url, json=data, auth=(self._user_name, self._pass_word))
        check_return(res)
        return res

    def delete(self, url: str) -> requests.Response:
        # res = requests.delete(self.url + url, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        res = requests.delete(self._api_url + url, auth=(self._user_name, self._pass_word))
        check_return(res)
        return res

    @try_request
    def list_simulations(self) -> List[Simulation]:
        res = self.get("simulations")
        return [Simulation.from_data(sim) for sim in res.json()]

    @try_request
    def get_simulation(self, sim_id: str) -> Simulation:
        res = self.get("simulation/" + sim_id)
        return Simulation.from_data(res.json())

    @try_request
    def query_simulations(self, constraints: List[str]) -> Simulation:
        params = {}
        for item in constraints:
            (key, value) = item.split('=')
            params[key] = value

        res = self.get("simulations", params)
        return [Simulation.from_data(sim) for sim in res.json()]

    @try_request
    def delete_simulation(self, sim_id: str) -> Dict:
        res = self.delete("simulation/" + sim_id)
        return res.json()

    @try_request
    def publish_simulation(self, sim_id: str) -> None:
        self.post("publish/" + sim_id, {})

    @try_request
    def push_simulation(self, simulation: Simulation) -> None:
        files: List[Tuple[str, Tuple[str, bytes, str]]] = [
            ("data", ("data", json.dumps({"simulation": simulation.data(recurse=True)}).encode(), "text/json"))
        ]

        for file in simulation.inputs:
            if file.type in (DataObject.Type.PATH, DataObject.Type.IMAS):
                path = os.path.join(file.directory, file.file_name)
                files.append(("inputs", (file.uuid.hex, read_bytes(path), "application/octet-stream")))

        for file in simulation.outputs:
            if file.type in (DataObject.Type.PATH, DataObject.Type.IMAS):
                path = os.path.join(file.directory, file.file_name)
                files.append(("outputs", (file.uuid.hex, read_bytes(path), "application/octet-stream")))

        self.put("simulations", data={}, files=files)

    @try_request
    def reset_database(self) -> None:
        self.post("reset", {})
