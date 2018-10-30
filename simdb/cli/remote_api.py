import os
import requests
import json
from typing import List, Dict, Callable
import gzip
import io
import urllib3

from ..database.models import Simulation
from .manifest import DataObject
from .. import __version__


urllib3.disable_warnings()


class FailedConnection(RuntimeError):
    pass


def try_request(func: Callable):
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


def check_return(res: requests.Response):
    if res.status_code != 200:
        data = res.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        else:
            res.raise_for_status()


class RemoteAPI:
    url = "https://localhost:5000/api/v%s/" % __version__
    user_name = "test"
    pass_word = "test"

    dir_path = os.path.dirname(os.path.realpath(__file__))
    cert_path = os.path.join(dir_path, "../remote/server.crt")

    def get(self, url: str) -> requests.Response:
        res = requests.get(self.url + url, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        check_return(res)
        return res

    def put(self, url: str, data: Dict, **kwargs) -> requests.Response:
        res = requests.put(self.url + url, json=data, auth=(self.user_name, self.pass_word), verify=self.cert_path, **kwargs)
        check_return(res)
        return res

    def post(self, url: str, data: Dict) -> requests.Response:
        res = requests.post(self.url + url, json=data, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        check_return(res)
        return res

    def delete(self, url: str) -> requests.Response:
        res = requests.delete(self.url + url, auth=(self.user_name, self.pass_word), verify=self.cert_path)
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
    def delete_simulation(self, sim_id: str) -> dict:
        res = self.delete("simulation/" + sim_id)
        return res.json()

    @try_request
    def publish_simulation(self, sim_id: str) -> None:
        self.post("publish/" + sim_id, {})

    @try_request
    def push_simulation(self, simulation: Simulation) -> None:
        files = [
            ("data", ("data", json.dumps({"simulation": simulation.data(recurse=True)}), "text/json"))
        ]
        for file in simulation.files:
            if file.type in (DataObject.Type.PATH, DataObject.Type.IMAS):
                path = os.path.join(file.directory, file.file_name)
                files.append(("files", (file.uuid.hex, read_bytes(path).decode(), "application/octet-stream")))

        self.put("simulations", data={}, files=files)

    @try_request
    def reset_database(self) -> None:
        self.post("reset", {})
