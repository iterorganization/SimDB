import os
import requests
import json
from typing import List, Dict

from ..database.models import Simulation
from .. import __version__


class FailedConnection(RuntimeError):
    pass


def try_request(func):
    def wrapped_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.ConnectionError:
            raise FailedConnection("Failed to connect to remote API")
    return wrapped_func


class RemoteAPI:
    url = "https://localhost:5000/api/v%s/" % __version__
    user_name = "test"
    pass_word = "test"
    cert_path = "/Users/jhollocombe/Projects/simdb/simdb/remote/server.crt"

    def get(self, url: str) -> requests.Response:
        res = requests.get(self.url + url, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        if res.status_code != 200:
            data = res.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            else:
                res.raise_for_status()
        return res

    def put(self, url: str, data: Dict, **kwargs) -> requests.Response:
        res = requests.put(self.url + url, json=data, auth=(self.user_name, self.pass_word), verify=self.cert_path, **kwargs)
        if res.status_code != 200:
            data = res.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            else:
                res.raise_for_status()
        return res

    def post(self, url: str, data: Dict) -> requests.Response:
        res = requests.post(self.url + url, json=data, auth=(self.user_name, self.pass_word), verify=self.cert_path)
        res.raise_for_status()
        return res

    @try_request
    def list_simulations(self) -> List[Simulation]:
        res = self.get("simulations")
        return [Simulation.from_data(sim) for sim in res.json()]

    @try_request
    def get_simulation(self, sim_id) -> Simulation:
        res = self.get("simulation/" + sim_id)
        return Simulation.from_data(res.json())

    @try_request
    def push_simulation(self, simulation: Simulation) -> None:
        files = [
            ("data", ("data", json.dumps({"simulation": simulation.data(recurse=True)}), "text/json"))
        ]
        for file in simulation.files:
            if file.type == "PATH":
                path = os.path.join(file.directory, file.file_name)
                files.append(("files", (file.uuid.hex, open(path, "rb"), "application/octet-stream")))

        # self.put("simulations", {"simulation": simulation.data(recurse=True)}, files=files)
        self.put("simulations", data={"simulation": simulation.data(recurse=True)}, files=files)

    @try_request
    def reset_database(self) -> None:
        self.post("reset", {})
