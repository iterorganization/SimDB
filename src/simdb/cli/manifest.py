import re
import sys
import os
from enum import Enum, auto
from typing import Iterable, Union, Dict, List, Tuple, Optional
import uri as urilib
from pathlib import Path


class InvalidManifest(Exception):
    """
    Exception to throw when a manifest fails to validate.
    """
    pass


def _expand_path(path: Path, base_path: Path) -> Path:
    if not path.is_absolute():
        if not base_path.is_absolute():
            raise ValueError('base_path must be absolute')
        return base_path / path
    return path


def _to_uri(uri_str: str, base_path: Path) -> Tuple["DataObject.Type", urilib.URI]:
    uri = urilib.URI(uri_str)
    if uri.scheme is None:
        raise ValueError("invalid uri: %s" % uri_str)
    if uri.scheme.name == 'file':
        uri = urilib.URI(uri, path=_expand_path(uri.path, base_path))
        return DataObject.Type.FILE, uri
    if uri.scheme.name == "imas":
        return DataObject.Type.IMAS, uri
    if uri.scheme.name == "uda":
        return DataObject.Type.UDA, uri
    if uri.scheme.name == "simdb":
        return DataObject.Type.UUID, uri
    raise InvalidManifest("invalid uri " + uri_str)


class DataObject:
    """
    Simulation data object, either a file, an IDS or an already registered object identifiable by the UUID.

    UUID: simdb:///<UUID>
    PATH: file:///<PATH>
    IMAS: imas:///?shot=<SHOT>&run=<RUN>&machine=<MACHINE>&user=<USER>
    UDA:  uda:///?signal=<SIGNAL>&source=<SOURCE>
    """
    class Type(Enum):
        UNKNOWN = auto()
        UUID = auto()
        FILE = auto()
        IMAS = auto()
        UDA = auto()

    type: Type = Type.UNKNOWN
    uri: urilib.URI = urilib.URI()

    def __init__(self, base_path: Path, uri: str) -> None:
        (self.type, self.uri) = _to_uri(uri, base_path)
        if self.type == DataObject.Type.UNKNOWN or not self.uri:
            raise InvalidManifest("invalid input")

    @property
    def name(self) -> str:
        return str(self.uri)


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
    def validate(self, values: Union[List, Dict]) -> None:
        pass


class ListValuesValidator(ManifestValidator):
    """
    Class for the validation of list items in the manifest.
    """
    def __init__(self, section_name: str = NotImplemented, expected_keys: Iterable = NotImplemented,
                 required_keys: Iterable = NotImplemented) -> None:
        self.section_name: str = section_name
        self.expected_keys: Iterable = expected_keys
        self.required_keys: Iterable = required_keys

    def validate(self, values: Union[list, dict]) -> None:
        if isinstance(values, dict):
            raise InvalidManifest("badly formatted manifest - %s should be provided as a list" % self.section_name)
        for item in values:
            if not isinstance(item, dict) or len(item) > 1:
                raise InvalidManifest("badly formatted manifest - %s values should be a name value pair" % self.section_name)
            name = list(item.keys())[0]
            if isinstance(self.expected_keys, tuple) and name not in self.expected_keys:
                raise InvalidManifest("unknown %s entry in manifest: %s" % (self.section_name, name))
            if isinstance(self.required_keys, tuple) and name not in self.required_keys:
                raise InvalidManifest("required %s key not found in manifest: %s" % (self.section_name, name))
            if name == 'path' and not os.path.isfile(list(item.values())[0]):
                raise InvalidManifest("invalid path to file in manifest: %s" % (list(item.values())[0]))


class InputsValidator(ListValuesValidator):
    """
    Validator for the manifest inputs list.
    """
    def __init__(self) -> None:
        self.section_name: str = "inputs"
        self.expected_keys: Iterable = ("uri",)
        super().__init__(self.section_name, self.expected_keys)


class ScriptsValidator(ListValuesValidator):
    """
    Validator for the manifest scripts list.
    """
    def __init__(self) -> None:
        self.section_name: str = "scripts"
        self.expected_keys: Iterable = ("name", "path",)
        super().__init__(self.section_name, self.expected_keys)


class OutputsValidator(ListValuesValidator):
    """
    Validator for the manifest outputs list.
    """
    def __init__(self) -> None:
        self.section_name: str = "outputs"
        # self.expected_keys: Iterable = ("path", "imas")
        self.expected_keys: Iterable = ("uri",)
        super().__init__(self.section_name, self.expected_keys)

class DescriptionValidator(ManifestValidator):
    """
    Validator for simulation description.
    """
    def validate(self, value):
        if not isinstance(value, str):
            raise InvalidManifest("description must be a string")

class MetaDataValidator(ListValuesValidator):
    """
    Validator for the manifest Metadata list.
    """
    def __init__(self) -> None:
        self.section_name: str = "metadata"
        self.expected_keys: Iterable = ("path", "values")
        super().__init__(self.section_name, self.expected_keys)


class DictValuesValidator(ManifestValidator):
    """
    Class for the validation of dictionary items in the manifest.
    """
    def __init__(self, section_name: str = NotImplemented, expected_keys: Iterable = NotImplemented,
                 required_keys: Iterable = NotImplemented) -> None:
        self.section_name: str = section_name
        self.expected_keys: Iterable = expected_keys
        self.required_keys: Iterable = required_keys

    def validate(self, values: Union[list, dict]) -> None:
        if isinstance(values, list):
            raise InvalidManifest("badly formatted manifest - %s should be provided as a dict" % self.section_name)

        for key in values.keys():
            if key not in self.expected_keys:
                if re.match(r"code[0-9]+", key):
                    for code_key in values[key]:
                        if code_key not in ("name", "repo", "commit"):
                            raise InvalidManifest("unknown %s.%s key in manifest: %s" % (self.section_name, key, code_key))
                else:
                    raise InvalidManifest("unknown %s key in manifest: %s" % (self.section_name, key))

        for key in self.required_keys:
            if isinstance(self.expected_keys, list) and key not in values.keys():
                raise InvalidManifest("required %s key not found in manifest: %s" % (self.section_name, key))


class WorkflowValidator(DictValuesValidator):
    """
    Validator for the manifest workflow dictionary.
    """
    def __init__(self) -> None:
        self.section_name: str = "workflow"
        self.expected_keys: Iterable = ("name", "developer", "date", "repo", "commit", "codes", "branch")
        self.required_keys: Iterable = ("name", "repo", "commit", "branch")
        super().__init__(self.section_name, self.expected_keys, self.required_keys)


def _update_dict(old: Dict, new: Dict) -> None:
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
    _data: Union[Dict, List, None] = None
    _path: str = ""
    _metadata: Dict = {}

    @property
    def metadata(self) -> Dict:
        return self._metadata

    @classmethod
    def from_template(cls) -> "Manifest":
        """
        Create an empty manifest from a template file.

        :return: A new manifest object.
        """
        manifest = cls()
        dir_path = Path(__file__).resolve().parent
        manifest.load(dir_path / "template.yaml")
        return manifest

    @property
    def inputs(self) -> Iterable[Source]:
        if isinstance(self._data, dict):
            return [Source(self._path, i["uri"]) for i in self._data["inputs"]]
        return []

    @property
    def outputs(self) -> Iterable[Sink]:
        if isinstance(self._data, dict):
            return [Sink(self._path, i["uri"]) for i in self._data["outputs"]]
        return []

    @property
    def workflow(self) -> Dict:
        if isinstance(self._data, dict):
            return self._data["workflow"]
        return {}

    @property
    def description(self) -> Dict:
        if isinstance(self._data, dict):
            return self._data["description"]
        return {}

    def _load_metadata(self, root_path: Path, path: Path):
        import yaml

        try:
            if not path.is_absolute():
                root_dir = root_path.absolute().parent
                path = root_dir / path
            with open(path) as metadata_file:
                _update_dict(self._metadata, yaml.load(metadata_file, Loader=yaml.SafeLoader))
        except yaml.YAMLError as err:
            raise InvalidManifest("failed to read metadata file %s - %s" % (path, err))

    def load(self, file_path: Path) -> None:
        """
        Load a manifest from the given file.

        :param file_path: Path to the file read.
        :return: None
        """
        import yaml

        self._path: Path = file_path
        with open(file_path) as file:
            try:
                self._data = yaml.load(file, Loader=yaml.SafeLoader)
            except yaml.YAMLError as err:
                raise InvalidManifest("badly formatted manifest - " + str(err))

        if isinstance(self._data, dict) and "metadata" in self._data:
            for item in self._data["metadata"]:
                if "path" in item:
                    self._load_metadata(file_path, item["path"])
                elif "values" in item:
                    _update_dict(self._metadata, item["values"])

    def save(self, file_path: Optional[Path]) -> None:
        """
        Save the manifest to the given file.

        :param file_path: The path to save the manifest to, or '-' to output to stdout.
        :return: None
        """
        import yaml

        if file_path is None or str(file_path) == "-":
            yaml.dump(self._data, sys.stdout, default_flow_style=False)
        else:
            if file_path.exists():
                raise Exception("file already exists")
            with open(file_path, "w") as out_file:
                yaml.dump(self._data, out_file, default_flow_style=False)

    def validate(self) -> None:
        """
        Validate the manifest object.

        :return: None
        """
        if self._data is None:
            raise InvalidManifest("failed to read manifest")
        if isinstance(self._data, list):
            raise InvalidManifest("badly formatted manifest - top level sections must be keys not a list")

        section_validators = {
            "inputs": InputsValidator(),
            "scripts": ScriptsValidator(),
            "outputs": OutputsValidator(),
            "workflow": WorkflowValidator(),
            "metadata": MetaDataValidator(),
            "description": DescriptionValidator()
        }

        for section in self._data.keys():
            if section not in section_validators.keys():
                raise InvalidManifest("unknown manifest section found: " + section)

        required_sections = ("inputs", "outputs", "workflow")
        for section in required_sections:
            if section not in self._data.keys():
                raise InvalidManifest("required manifest section not found: " + section)

        for name, values in self._data.items():
            section_validators[name].validate(values)
