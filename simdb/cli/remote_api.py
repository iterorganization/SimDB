import requests
from typing import List

from ..database.models import Simulation


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
    def __init__(self):
        self.url = "http://localhost:5000/api/v0.1/"

    @try_request
    def list(self) -> List[Simulation]:
        res = requests.get(self.url + "simulations")
        return [Simulation.from_data(sim) for sim in res.json()]

    @try_request
    def get(self, sim_id) -> Simulation:
        res = requests.get(self.url + "simulation/" + sim_id)
        return Simulation.from_data(res.json())

    @try_request
    def push(self, simulation: Simulation):
        res = requests.put(self.url + "simulations", json={"simulation": simulation.data(recurse=True)})
        return res

    @try_request
    def reset(self):
        res = requests.post(self.url + "reset")
        return res
