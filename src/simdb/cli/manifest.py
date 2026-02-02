import glob
import os
import re
import urllib
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Iterable, List, Optional, TextIO, Tuple, Type, Union

import numpy as np
import yaml

from simdb.uri import URI


class InvalidManifest(Exception):
    """Exception to throw when a manifest fails to validate."""

    pass


class InvalidAlias(InvalidManifest):
    """Exception to throw when the alias specified in the manifest is invalid."""

    pass


def _expand_path(path: Path, base_path: Path) -> Path:
    os.environ["MANIFEST_DIR"] = str(base_path)
    path = Path(os.path.expanduser(os.path.expandvars(path)))
    path = Path(str(path).replace("//", "/"))
    if not path.is_absolute():
        if not base_path.is_absolute():
            raise ValueError("base_path must be absolute")
        return base_path / path
    else:
        # Expand any /./ and /../ in absolute path
        path = os.path.abspath(path)
    return path


def _to_uri(uri_str: str, base_path: Path) -> Tuple["DataObject.Type", "URI"]:
    from simdb.uri import URI

    uri = URI(uri_str)
    if uri.authority:
        raise InvalidManifest(f"invalid uri: {uri_str} - path must be absolute")
    if uri.scheme is None:
        raise InvalidManifest(f"invalid uri: {uri_str} - no scheme provided")
    if uri.scheme == "file":
        uri = URI(uri, path=_expand_path(uri.path, base_path))
        return DataObject.Type.FILE, uri
    if uri.scheme == "imas":
        if "path" not in uri.query and not all(
            ("shot" in uri.query, "run" in uri.query, "database" in uri.query)
        ):
            raise InvalidManifest(
                f"invalid uri: {uri_str} - no path or (shot, run, database) provided in IMAS uri"
            )
        return DataObject.Type.IMAS, uri
    if uri.scheme == "uda":
        return DataObject.Type.UDA, uri
    if uri.scheme == "simdb":
        return DataObject.Type.UUID, uri
    raise InvalidManifest(f"invalid uri: {uri_str}")


class DataObject:
    """
    Simulation data object, either a file, an IDS or an already registered object identifiable by the UUID.

    PATH: file:///<PATH>
    IMAS: imas:<BACKEND>?path=<PATH>
    """

    class Type(Enum):
        UNKNOWN = auto()
        UUID = auto()
        FILE = auto()
        IMAS = auto()
        UDA = auto()

    type: Type = Type.UNKNOWN
    uri: Union[URI, None] = None

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

    version: int

    def __init__(self, version: int):
        self.version = version

    def validate(self, values: Union[List, Dict]) -> None:
        pass


class ListValuesValidator(ManifestValidator):
    """
    Class for the validation of list items in the manifest.
    """

    def __init__(
        self,
        version: int,
        section_name: str = NotImplemented,
        expected_keys: Iterable = NotImplemented,
        required_keys: Iterable = NotImplemented,
    ) -> None:
        self.section_name: str = section_name
        self.expected_keys: Iterable = expected_keys
        self.required_keys: Iterable = required_keys
        super().__init__(version)

    def validate(self, values: Union[list, dict]) -> None:
        if values is None:
            return
        if isinstance(values, dict):
            raise InvalidManifest(
                f"badly formatted manifest - {self.section_name} should be provided as a list"
            )
        for item in values:
            if not isinstance(item, dict) or len(item) > 1:
                raise InvalidManifest(
                    f"badly formatted manifest - {self.section_name} values should be a name value pair"
                )
            name = next(iter(item))

            if isinstance(self.required_keys, tuple) and name not in self.required_keys:
                raise InvalidManifest(
                    f"required {self.section_name} key not found in manifest: {name}"
                )


class DictValuesValidator(ManifestValidator):
    """
    Class for the validation of dictionary items in the manifest.
    """

    def __init__(
        self,
        version: int,
        section_name: str = NotImplemented,
        expected_keys: Iterable = NotImplemented,
        required_keys: Iterable = NotImplemented,
    ) -> None:
        self.section_name: str = section_name
        self.expected_keys: Iterable = expected_keys
        self.required_keys: Iterable = required_keys
        super().__init__(version)

    def validate(self, values: Union[list, dict]) -> None:
        if isinstance(values, list):
            raise InvalidManifest(
                f"badly formatted manifest - {self.section_name} should be provided as a dict"
            )

        for key in values:
            if key not in self.expected_keys:
                if re.match(r"code[0-9]+", key):
                    for code_key in values[key]:
                        if code_key not in ("name", "repo", "commit"):
                            raise InvalidManifest(
                                f"unknown {self.section_name}.{key} key in manifest: {code_key}"
                            )
                else:
                    raise InvalidManifest(
                        f"unknown {self.section_name} key in manifest: {key}"
                    )

        for key in self.required_keys:
            if isinstance(self.expected_keys, list) and key not in values:
                raise InvalidManifest(
                    f"required {self.section_name} key not found in manifest: {key}"
                )


class DataObjectValidator(ListValuesValidator):
    """
    Validator for the manifest data objects (inputs or outputs).
    """

    def __init__(self, version: int, section_name: str) -> None:
        if version == 0:
            expected_keys = ("uuid", "path", "imas", "uda")
        elif version > 0:
            expected_keys = ("uri",)
        else:
            raise KeyError("Invalid version.")
        super().__init__(version, section_name, expected_keys)

    def validate(self, values: Union[list, dict]) -> None:
        from simdb.uri import URI

        super().validate(values)
        if values is None:
            return
        seen_uris = set()
        for value in values:
            if self.version > 0:
                uri = URI(value["uri"])
                if uri.scheme not in ("uda", "file", "imas"):
                    raise InvalidManifest(f"unknown uri scheme: {uri.scheme}")
                if str(uri) in seen_uris:
                    raise InvalidManifest(
                        f"Duplicate URI found in {self.section_name}: {uri}"
                    )
                seen_uris.add(str(uri))


class InputsValidator(DataObjectValidator):
    """
    Validator for the manifest inputs list.
    """

    def __init__(self, version):
        super().__init__(version, "inputs")


class OutputsValidator(DataObjectValidator):
    """
    Validator for the manifest outputs list.
    """

    def __init__(self, version):
        super().__init__(version, "outputs")


class VersionValidator(ManifestValidator):
    """
    Validator for manifest version.
    """

    def __init__(self, version: int):
        super().__init__(version)

    def validate(self, value):
        if not isinstance(value, int):
            raise InvalidManifest("version must be an integer")


class AliasValidator(ManifestValidator):
    """
    Validator for simulation alias.
    """

    def __init__(self, version: int):
        super().__init__(version)

    def validate(self, value):
        if not isinstance(value, str):
            raise InvalidManifest("alias must be a string")
        if urllib.parse.quote(value) != value:
            raise InvalidAlias(f"illegal characters in alias: {value}")


class DescriptionValidator(ManifestValidator):
    """
    Validator for simulation description.
    """

    pass


class ResponsibleValidator(ManifestValidator):
    """
    Validator for simulation Responsible.
    """

    pass


def ndarray_constructor(
    loader: yaml.SafeLoader, node: yaml.nodes.MappingNode
) -> np.ndarray:
    mapping = loader.construct_mapping(node, deep=True)
    return np.array(mapping["data"], mapping.get("dtype", None))


def get_loader() -> Type[yaml.SafeLoader]:
    loader = yaml.SafeLoader
    loader.add_constructor("!ndarray", ndarray_constructor)
    return loader


class MetaDataValidator(ListValuesValidator):
    """
    Validator for the manifest Metadata list.
    """

    forbidden_characters = (":", "=", "#")

    def __init__(self, version: int) -> None:
        section_name = "metadata"
        required_keys = ("machine", "code", "description")
        super().__init__(version, section_name, required_keys)

    def validate(self, values: Union[list, dict]) -> None:
        super().validate(values)

        for item in values:
            name = next(iter(item))
            for char in MetaDataValidator.forbidden_characters:
                if char in name:
                    raise InvalidManifest(
                        f"invalid metadata field name {name}- contains forbidden character {char}"
                    )


class WorkflowValidator(DictValuesValidator):
    """
    Validator for the manifest workflow dictionary.
    """

    def __init__(self, version: int) -> None:
        section_name = "workflow"
        if version == 0:
            expected_keys = ("name", "git", "repo", "commit", "codes")
            required_keys = ("name", "commit", "codes")
        elif version == 1:
            expected_keys = (
                "name",
                "developer",
                "date",
                "repo",
                "commit",
                "codes",
                "branch",
            )
            required_keys = ("name", "repo", "commit", "branch")
        else:
            raise KeyError("Invalid version.")
        super().__init__(version, section_name, expected_keys, required_keys)


def _update_dict(old: Dict, new: Dict) -> None:
    for k, v in new.items():
        if k in old:
            if isinstance(old[k], list):
                old[k].append(v)
            else:
                old[k] = [old[k], v]
        else:
            old[k] = v


class Manifest:
    """
    Class to handle reading, writing & validation of simulation manifest files.
    """

    def __init__(self) -> None:
        self._data: Union[Dict, List, None] = None
        self._path: Path = Path()
        self._metadata: Dict = {}

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
        sources = []
        base_path = self._path.absolute().parent
        if (
            isinstance(self._data, dict)
            and "inputs" in self._data
            and self._data["inputs"]
        ):
            for i in self._data["inputs"]:
                source = Source(base_path, i["uri"])
                if source.type == DataObject.Type.FILE:
                    names = glob.glob(str(source.uri.path))
                    if not names:
                        raise InvalidManifest(
                            f"No files found matching path {source.uri.path}"
                        )
                    for name in names:
                        sources.append(Source(base_path, "file://" + name))
                else:
                    sources.append(source)
        return sources

    @property
    def outputs(self) -> Iterable[Sink]:
        sinks = []
        base_path = self._path.absolute().parent
        if isinstance(self._data, dict) and self._data["outputs"]:
            for i in self._data["outputs"]:
                sink = Sink(base_path, i["uri"])
                if sink.type == DataObject.Type.FILE:
                    names = glob.glob(str(sink.uri.path))
                    for name in names:
                        sinks.append(Sink(base_path, "file://" + name))
                else:
                    sinks.append(sink)
        return sinks

    @property
    def alias(self) -> Optional[str]:
        if isinstance(self._data, dict):
            return self._data.get("alias", None)
        return None

    @property
    def responsible_name(self) -> Optional[str]:
        if isinstance(self._data, dict):
            return self._data.get("responsible_name", None)
        return None

    @property
    def version(self) -> int:
        if isinstance(self._data, dict):
            return self._data.get("version", 2)
        return 0

    @property
    def manifest_version(self) -> int:
        if isinstance(self._data, dict):
            return self._data.get("manifest_version", 2)
        return 0

    def _load_metadata(self, root_path: Path, path: Path):
        try:
            if not path.is_absolute():
                root_dir = root_path.absolute().parent
                path = root_dir / path
            with open(path) as metadata_file:
                _update_dict(
                    self._metadata, yaml.load(metadata_file, Loader=get_loader())
                )
        except yaml.YAMLError as err:
            raise InvalidManifest(f"failed to read metadata file {path}") from err

    def _convert_version(self):
        if self.version == 0:
            self._convert_metadata()
            self._data["inputs"] = self._convert_files(self._data["inputs"])
            self._data["outputs"] = self._convert_files(self._data["outputs"])
        self._data["version"] = 1

    def _convert_metadata(self) -> None:
        for item in ("description", "workflow"):
            if item in self._data:
                self._metadata[item] = self._data[item]
                del self._data[item]

        for key, value in self._metadata.items():
            if key == "workflow":
                if "git" in value:
                    value["repo"] = value["git"]
                    del value["git"]
                if "codes" in value:
                    codes = value["codes"]
                    new_codes = []
                    for code in codes:
                        for _, v in code.items():
                            new_codes.append(v)
                    value["codes"] = new_codes

    @classmethod
    def _convert_files(cls, files: List[Dict[str, str]]) -> List[Dict[str, "URI"]]:
        from simdb.uri import URI

        scheme_map = {
            "uuid": "simdb",
            "path": "file",
            "imas": "imas",
            "uda": "uda",
        }

        new_files = []
        for file in files:
            for k, v in file.items():
                new_files.append({"uri": URI(scheme=scheme_map[k], path=v)})
        return new_files

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
                self._data = yaml.load(file, Loader=get_loader())
            except yaml.YAMLError as err:
                raise InvalidManifest("badly formatted manifest") from err

        if isinstance(self._data, dict) and "metadata" in self._data:
            self._data["metadata"] or []
            self._metadata["metadata"] = self._data["metadata"]

    def save(self, out_file: TextIO) -> None:
        """
        Save the manifest to the given file.

        :param out_file: The output text stream to write the manifest to.
        :return: None
        """
        import yaml

        yaml.dump(self._data, out_file, default_flow_style=False)

    def validate(self) -> None:
        """
        Validate the manifest object.

        :return: None
        """
        if self._data is None:
            raise InvalidManifest("failed to read manifest")
        if isinstance(self._data, list):
            raise InvalidManifest(
                "badly formatted manifest - top level sections must be keys not a list"
            )

        if "manifest_version" not in self._data:
            print("warning: no version given in manifest, assuming version 2.")

        version = self.version

        if version == 2:
            section_validators = {
                "manifest_version": VersionValidator(version),
                "alias": AliasValidator(version),
                "inputs": InputsValidator(version),
                "outputs": OutputsValidator(version),
                "metadata": MetaDataValidator(version),
                "responsible_name": ResponsibleValidator(version),
            }
        else:
            raise InvalidManifest(f"Unknown manifest version {version}.")

        for section in self._data:
            if section not in section_validators:
                raise InvalidManifest(f"Unknown manifest section found {section}.")

        required_sections = ("manifest_version", "outputs", "inputs")
        for section in required_sections:
            if section not in self._data:
                raise InvalidManifest(
                    f"Required manifest section '{section}' not found."
                )

        for name, values in self._data.items():
            section_validators[name].validate(values)
        self._convert_version()
