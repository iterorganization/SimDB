import sys
import os
from enum import Enum, auto
from typing import Iterable, Union, Dict, List


class InvalidManifest(Exception):
    """
    Exception to throw when a manifest fails to validate.
    """
    pass


def _expand_path(base_path: str, path: str) -> str:
    if os.path.abspath(path) != path:
        path = os.path.join(os.path.dirname(os.path.abspath(base_path)), path)
    return path


class DataObject:
    """
    Simulation data object, either a file, an IDS or an already registered object identifiable by the UUID.
    """
    class Type(Enum):
        UNKNOWN = auto()
        UUID = auto()
        PATH = auto()
        IMAS = auto()
        UDA = auto()

    type: Type = Type.UNKNOWN
    uuid: str = None
    path: str = None
    imas: Dict = None
    uda: Dict = None

    def __init__(self, base_path: str, values: Dict) -> None:
        if "uuid" in values:
            self.uuid = values["uuid"]
            self.type = DataObject.Type.UUID
        elif "path" in values:
            self.path = _expand_path(base_path, values["path"])
            self.type = DataObject.Type.PATH
        elif "imas" in values:
            self.imas = values["imas"]
            self.type = DataObject.Type.IMAS
        elif "uda" in values:
            self.uda = values["uda"]
            self.type = DataObject.Type.UDA
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
        elif self.type == DataObject.Type.UDA:
            return "UDA(signal={}, shot={}, run={})".format(self.uda["signal"], self.uda["shot"], self.uda["run"])
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
            if isinstance(self.expected_keys, list) and name not in self.expected_keys:
                raise InvalidManifest("unknown %s entry in manifest: %s" % (self.section_name, name))
            if isinstance(self.required_keys, list) and name not in self.required_keys:
                raise InvalidManifest("required %s key not found in manifest: %s" % (self.section_name, name))
            if name == 'path' and not os.path.isfile(list(item.values())[0]):
                raise InvalidManifest("invalid path to file in manifest: %s" % (list(item.values())[0]))


class InputsValidator(ListValuesValidator):
    """
    Validator for the manifest inputs list.
    """
    def __init__(self) -> None:
        self.section_name: str = "inputs"
        self.expected_keys: Iterable = ("uuid", "path", "imas", "uda")
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
        self.expected_keys: Iterable = ("path", "imas")
        super().__init__(self.section_name, self.expected_keys)


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
            if isinstance(self.expected_keys, list) and key not in self.expected_keys:
                raise InvalidManifest("unknown %s key in manifest: %s" % (self.section_name, key))

        for key in self.required_keys:
            if isinstance(self.expected_keys, list) and key not in values.keys():
                raise InvalidManifest("required %s key not found in manifest: %s" % (self.section_name, key))

        # verify git commit

        cmd = "git ls-remote {} {}; echo $?".format(values["git"], values["commit"])
        #cmd = "git ls-remote --exit-code ssh://git@git.iter.org/imas/data-dictionary.git 6aaffc84dd5178c3b4f20c2892db6701dfca1dc7; echo $?"

        if int(os.popen(cmd).read()) == 2:
            raise InvalidManifest("invalid git repository commit specified in manifest: %s" %
                                  (self.section_name, "{} {}".format(values["git"], values["commit"])))


class WorkflowValidator(DictValuesValidator):
    """
    Validator for the manifest workflow dictionary.
    """
    def __init__(self) -> None:
        self.section_name: str = "workflow"
        self.expected_keys: Iterable = ("name", "developer", "date", "git", "commit", "codes", "branch")
        self.required_keys: Iterable = ("name", "git", "commit", "branch")
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
        dir_path = os.path.dirname(os.path.realpath(__file__))
        manifest.load(os.path.join(dir_path, "template.yaml"))
        return manifest

    @property
    def inputs(self) -> Iterable[Source]:
        if isinstance(self._data, dict):
            return [Source(self._path, i) for i in self._data["inputs"]]
        return []

    @property
    def outputs(self) -> Iterable[Sink]:
        if isinstance(self._data, dict):
            return [Sink(self._path, i) for i in self._data["outputs"]]
        return []

    @property
    def workflow(self) -> Dict:
        if isinstance(self._data, dict):
            return self._data["workflow"]
        return {}

    def _load_metadata(self, root_path, path):
        import yaml

        try:
            if os.path.abspath(path) != path:
                root_dir = os.path.dirname(os.path.abspath(root_path))
                path = os.path.join(root_dir, path)
            with open(path) as metadata_file:
                _update_dict(self._metadata, yaml.load(metadata_file))
        except yaml.YAMLError as err:
            raise InvalidManifest("failed to read metadata file %s - %s" % (path, err))

    def load(self, file_path) -> None:
        """
        Load a manifest from the given file.

        :param file_path: Path to the file read.
        :return: None
        """
        import yaml

        self._path = file_path
        with open(file_path) as file:
            try:
                self._data = yaml.load(file, Loader=yaml.FullLoader)
            except yaml.YAMLError as err:
                raise InvalidManifest("badly formatted manifest - " + str(err))

        if isinstance(self._data, dict) and "metadata" in self._data:
            for item in self._data["metadata"]:
                if "path" in item:
                    self._load_metadata(file_path, item["path"])
                elif "values" in item:
                    _update_dict(self._metadata, item["values"])

    def save(self, file_path: str) -> None:
        """
        Save the manifest to the given file.

        :param file_path: The path to save the manifest to, or '-' to output to stdout.
        :return: None
        """
        import yaml

        if file_path is None or file_path == "-":
            yaml.dump(self._data, sys.stdout, default_flow_style=False)
        else:
            if os.path.exists(file_path):
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
        }

        for section in self._data.keys():
            if section not in section_validators.keys():
                raise InvalidManifest("unknown manifest section found: " + section)

        required_sections = ("inputs", "outputs", "workflow")
        for section in required_sections:
            if section not in self._data.keys():
                raise InvalidManifest("required manifest section not found: " + section)

        for name, values in self._data.items():
            #print("******", name)
            section_validators[name].validate(values)
