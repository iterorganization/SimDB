import requests
from typing import List
import json

from ..database.models import Simulation


class RemoteAPI:
    def __init__(self):
        self.url = "http://localhost:5000/api/v0.1/"

    def list(self) -> List[Simulation]:
        res = requests.get(self.url + "simulations")
        return [Simulation.from_data(sim) for sim in res.json()]

    def get(self, sim_id) -> Simulation:
        res = requests.get(self.url + "simulation/" + sim_id)
        return Simulation.from_data(res.json())

    def push(self, simulation: Simulation):
        res = requests.put(self.url + "simulations", json={"simulation": simulation.data()})
        return res