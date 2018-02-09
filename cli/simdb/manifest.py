import yaml
import sys
import os
from enum import Enum, auto
from typing import Iterable
import hashlib


class InvalidManifest(Exception):
    pass


class Source:
    class Type(Enum):
        UNKNOWN = auto()
        UUID = auto()
        PATH = auto()
        IMAS = auto()

    type: Type = Type.UNKNOWN
    uuid: str = None
    path: str = None
    imas: dict = None

    def __init__(self, values):
        if "uuid" in values:
            self.uuid = values["uuid"]
            self.type = Source.Type.UUID
        elif "path" in values:
            self.path = values["path"]
            self.type = Source.Type.PATH
        elif "imas" in values:
            self.imas = values["imas"]
            self.type = Source.Type.IMAS
        else:
            raise InvalidManifest("invalid input")

    @property
    def checksum(self) -> str:
        sha1 = hashlib.sha1()
        with open(self.path, "rb") as file:
            sha1.update(file)
        return sha1.hex_digest()

    @property
    def name(self) -> str:
        if self.type == Source.Type.UUID:
            return self.uuid
        elif self.type == Source.Type.PATH:
            return os.path.basename(self.path)
        elif self.type == Source.Type.IMAS:
            return self.imas["tree_name"]


class Manifest:

    def __init__(self):
        self.data = None

    @classmethod
    def from_template(cls):
        manifest = cls()
        dir_path = os.path.dirname(os.path.realpath(__file__))
        manifest.load(dir_path + "/template.yaml")
        return manifest

    def load(self, file_name):
        with open(file_name) as file:
            self.data = yaml.load(file)

    def validate(self):
        # * Check diff files exist
        # * Check contents of diff file - do they match the git diff provided
        pass

    @property
    def inputs(self) -> Iterable[Source]:
        return [Source(i) for i in self.data["inputs"]]

    @property
    def outputs(self) -> Iterable[Source]:
        return [Source(i) for i in self.data["outputs"]]

    def save(self, file_name: str) -> None:
        if file_name is None or file_name == "-":
            yaml.dump(self.data, sys.stdout, default_flow_style=False)
        else:
            if os.path.exists(file_name):
                raise Exception("file already exists")
            with open(file_name, "w") as out_file:
                yaml.dump(self.data, out_file, default_flow_style=False)
