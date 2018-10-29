import yaml
import sys
import os
from enum import Enum, auto
from typing import Iterable, Union, List


class InvalidManifest(Exception):
    """
    Exception to throw when a manifest fails to validate.
    """
    pass


class DataObject:
    """
    Simulation data object, either a file, an IDS or an already registered object identifiable by the UUID.
    """
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
            self.type = DataObject.Type.UUID
        elif "path" in values:
            self.path = values["path"]
            self.type = DataObject.Type.PATH
        elif "imas" in values:
            self.imas = values["imas"]
            self.type = DataObject.Type.IMAS
        else:
            raise InvalidManifest("invalid input")

    @property
    def name(self) -> str:
        if self.type == DataObject.Type.UUID:
            return self.uuid
        elif self.type == DataObject.Type.PATH:
            return self.path
        elif self.type == DataObject.Type.IMAS:
            return "IDS(shot={}, run={})".format(self.imas["shot"], self.imas["run"])
        return DataObject.Type.UUID.name


class Source(DataObject):
    """
    Simulation data inputs.
    """
    pass


class Sink(DataObject):
    """
    Simulation data outputs.
    """
    pass


class ManifestValidator:
    """
    Base class for validation of manifests.
    """
    def validate(self, values: Union[list, dict]) -> None:
        pass


class ListValuesValidator(ManifestValidator):
    """
    Class for the validation of list items in the manifest.
    """
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
    """
    Validator for the manifest inputs list.
    """
    section_name: str = "input"
    expected_keys: Iterable = ("uuid", "path", "imas")


class ScriptsValidator(ListValuesValidator):
    """
    Validator for the manifest scripts list.
    """
    section_name: str = "script"
    expected_keys: Iterable = ("path",)


class OutputsValidator(ListValuesValidator):
    """
    Validator for the manifest outputs list.
    """
    section_name: str = "output"
    expected_keys: Iterable = ("path", "imas")


class MetaDataValidator(ListValuesValidator):
    """
    Validator for the manifest outputs list.
    """
    section_name: str = "metadata"
    expected_keys: Iterable = ("path", "values")


class DictValuesValidator(ManifestValidator):
    """
    Class for the validation of dictionary items in the manifest.
    """
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
    """
    Validator for the manifest workflow dictionary.
    """
    section_name: str = "workflow"
    expected_keys: Iterable = ("name", "git", "commit", "codes")
    required_keys: Iterable = ("name", "git", "commit", "codes")


def _update_dict(old: dict, new: dict) -> None:
    for k, v in new.items():
        if k in old:
            if type(old[k]) == list:
                old[k].append(v)
            else:
                old[k] = [old[k], v]
        else:
            old[k] = v


class Manifest:
    """
    Class to handle reading, writing & validation of simulation manifest files.
    """
    data: Union[dict, list, None] = None # :int
    """
    data: int
    """
    metadata: dict = {}

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
    def outputs(self) -> Iterable[Sink]:
        if isinstance(self.data, dict):
            return [Sink(i) for i in self.data["outputs"]]
        return []

    def _load_metadata(self, path):
        try:
            with open(path) as metadata_file:
                _update_dict(self.metadata, yaml.load(metadata_file))
        except yaml.YAMLError as err:
            raise InvalidManifest("failed to read metadata file %s - %s" % (path, err))

    def load(self, file_path) -> None:
        """
        Load a manifest from the given file.

        :param file_path: Path to the file read.
        :return: None
        """
        with open(file_path) as file:
            try:
                self.data = yaml.load(file)
            except yaml.YAMLError as err:
                raise InvalidManifest("badly formatted manifest - " + str(err))

        if "metadata" in self.data:
            for item in self.data["metadata"]:
                if "path" in item:
                    self._load_metadata(item["path"])
                elif "values" in item:
                    _update_dict(self.metadata, item["values"])

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
            "metadata": MetaDataValidator(),
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
