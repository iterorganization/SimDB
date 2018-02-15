import yaml
import sys
import os
from enum import Enum, auto
from typing import Iterable, Union
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
            for chunk in iter(lambda: file.read(4096), b""):
                sha1.update(chunk)
        return sha1.hexdigest()

    @property
    def name(self) -> str:
        if self.type == Source.Type.UUID:
            return self.uuid
        elif self.type == Source.Type.PATH:
            return self.path
            return self.path
        elif self.type == Source.Type.IMAS:
            return self.imas["tree_name"]
        return Source.Type.UUID.name


class Validator:
    def validate(self, values: Union[list, dict]) -> None:
        pass


class ListValuesValidator(Validator):
    section_name: str = NotImplemented
    expected_keys: Iterable = NotImplemented

    def validate(self, values: Union[list, dict]) -> None:
        if isinstance(values, dict):
            raise InvalidManifest("badly formatted manifest - %ss should be provided as a list" % self.section_name)
        for item in values:
            if not isinstance(item, dict) or len(item) > 1:
                raise InvalidManifest("badly formatted manifest - %s values should be a name value pair" % self.section_name)
            name = list(item.keys())[0]
            if name not in self.expected_keys:
                raise InvalidManifest("unknown %s entry: %s" % (self.section_name, name))


class InputsValidator(ListValuesValidator):
    section_name: str = "input"
    expected_keys: Iterable = ("uuid", "path", "imas")


class ScriptsValidator(ListValuesValidator):
    section_name: str = "script"
    expected_keys: Iterable = ("name",)


class OutputsValidator(ListValuesValidator):
    section_name: str = "output"
    expected_keys: Iterable = ("path", "imas")


class DictValuesValidator(Validator):
    section_name: str = NotImplemented
    expected_keys: Iterable = NotImplemented
    required_keys: Iterable = NotImplemented

    def validate(self, values: Union[list, dict]) -> None:
        if isinstance(values, list):
            raise InvalidManifest("badly formatted manifest - %s should be provided as a dict" % self.section_name)

        for key in values.keys():
            if key not in self.expected_keys:
                raise InvalidManifest("unknown %s key: %s" % (self.section_name, key))

        for key in self.required_keys:
            if key not in values.keys():
                raise InvalidManifest("required %s key not found: %s" % (self.section_name, key))


class WorkflowValidator(DictValuesValidator):
    section_name: str = "workflow"
    expected_keys: Iterable = ("name", "git", "branch", "commit", "codes")
    required_keys: Iterable = ("name", "git", "branch", "commit", "codes")


class Manifest:
    """
    Class to handle reading, writing & validation of simulation manifest files.
    """
    data: Union[dict, list, None] = None

    @classmethod
    def from_template(cls) -> "Manifest":
        """
        Create an empty manifest from a template file.

        :return: A new manifest object.
        """
        manifest = cls()
        dir_path = os.path.dirname(os.path.realpath(__file__))
        manifest.load(os.path.join(dir_path, "template.yaml"))
        return manifest

    @property
    def inputs(self) -> Iterable[Source]:
        if isinstance(self.data, dict):
            return [Source(i) for i in self.data["inputs"]]
        return []

    @property
    def outputs(self) -> Iterable[Source]:
        if isinstance(self.data, dict):
            return [Source(i) for i in self.data["outputs"]]
        return []

    def load(self, file_path) -> None:
        """
        Load a manifest from the given file.

        :param file_path: Path to the file read.
        :return: None
        """
        with open(file_path) as file:
            try:
                self.data = yaml.load(file)
            except yaml.YAMLError as error:
                raise InvalidManifest("badly formatted manifest - " + str(error))

    def save(self, file_path: str) -> None:
        """
        Save the manifest to the given file.

        :param file_path: The path to save the manifest to, or '-' to output to stdout.
        :return: None
        """
        if file_path is None or file_path == "-":
            yaml.dump(self.data, sys.stdout, default_flow_style=False)
        else:
            if os.path.exists(file_path):
                raise Exception("file already exists")
            with open(file_path, "w") as out_file:
                yaml.dump(self.data, out_file, default_flow_style=False)

    def validate(self) -> None:
        """
        Validate the manifest object.

        :return: None
        """
        if self.data is None:
            raise InvalidManifest("failed to read manifest")
        if isinstance(self.data, list):
            raise InvalidManifest("badly formatted manifest - top level sections must be keys not a list")

        section_validators = {
            "inputs": InputsValidator(),
            "scripts": ScriptsValidator(),
            "outputs": OutputsValidator(),
            "workflow": WorkflowValidator(),
        }

        for section in self.data.keys():
            if section not in section_validators.keys():
                raise InvalidManifest("unknown manifest section found: " + section)

        required_sections = ("inputs", "outputs", "workflow")
        for section in required_sections:
            if section not in self.data.keys():
                raise InvalidManifest("required section not found: " + section)

        for name, values in self.data.items():
            section_validators[name].validate(values)
