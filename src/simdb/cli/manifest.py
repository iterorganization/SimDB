import os
import urllib.parse
import warnings
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    TextIO,
    Tuple,
    Union,
)

import numpy as np
import yaml
from netCDF4 import Dataset
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    UrlConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from simdb.imas.utils import SimDBUrl

# Path to an item in the manifest, e.g. ("inputs", 0, "uri").
Location = Tuple[Union[str, int], ...]


@dataclass(frozen=True)
class ManifestIssue:
    """A single problem found in a manifest file.

    ``line`` and ``column`` are 1-based positions in the manifest file, when known.
    """

    message: str
    location: Location = ()
    line: Optional[int] = None
    column: Optional[int] = None

    @classmethod
    def at(
        cls, message: str, mark: Optional[yaml.Mark], location: Location = ()
    ) -> "ManifestIssue":
        """Create an issue positioned at a (0-based) YAML source mark, if known."""
        if mark is None:
            return cls(message, location)
        return cls(message, location, mark.line + 1, mark.column + 1)

    def describe(self, path: Path) -> str:
        position = str(path)
        if self.line is not None:
            position += f":{self.line}"
            if self.column is not None:
                position += f":{self.column}"
        if self.location:
            return f"{position}: {_format_location(self.location)}: {self.message}"
        return f"{position}: {self.message}"


class InvalidManifestError(ValueError):
    """Exception raised when a manifest file cannot be read or fails to validate."""

    def __init__(self, path: Path, errors: List[ManifestIssue]) -> None:
        self.path = path
        self.errors = errors
        count = f"{len(errors)} error{'s' if len(errors) != 1 else ''}"
        lines = [f"invalid manifest {path} ({count}):"]
        lines += [f"  {error.describe(path)}" for error in errors]
        super().__init__("\n".join(lines))

    @classmethod
    def from_yaml_error(cls, path: Path, err: yaml.YAMLError) -> "InvalidManifestError":
        if not isinstance(err, yaml.MarkedYAMLError) or err.problem is None:
            return cls(path, [ManifestIssue(str(err))])
        message = err.problem
        if err.context and err.context_mark:
            message += f" ({err.context} at line {err.context_mark.line + 1})"
        mark = err.problem_mark or err.context_mark
        return cls(path, [ManifestIssue.at(message, mark)])

    @classmethod
    def from_validation_error(
        cls,
        path: Path,
        err: ValidationError,
        marks: Dict[Location, yaml.Mark],
        overridden: Iterable[str] = (),
    ) -> "InvalidManifestError":
        """Convert pydantic errors into issues positioned in the manifest file.

        Values in ``overridden`` were not read from the file, so errors in them
        are not given a file position.
        """
        overridden = set(overridden)
        errors = []
        for error in err.errors(include_url=False):
            location = tuple(error["loc"])
            message = error["msg"]
            ctx = error.get("ctx") or {}
            if error["type"] == "value_error" and "error" in ctx:
                # Drop pydantic's "Value error, " prefix from our own validators.
                message = str(ctx["error"])
            elif error["type"] == "model_type":
                # Drop pydantic's "... or instance of <Model>" suffix.
                message = "Input should be a valid dictionary"
            if location and location[0] in overridden:
                message += " (overridden value, not from the file)"
                mark = None
            else:
                mark = _find_mark(marks, location)
            errors.append(ManifestIssue.at(message, mark, location))
        # Report in file order, with errors that have no position last.
        errors.sort(key=lambda e: (e.line is None, e.line or 0, e.column or 0))
        return cls(path, errors)


def _format_location(location: Location) -> str:
    """Format a location as e.g. ``inputs[0].uri``."""
    text = ""
    for part in location:
        if isinstance(part, int):
            text += f"[{part}]"
        else:
            text += f".{part}" if text else str(part)
    return text


def _source_marks(
    node: yaml.Node, location: Location = ()
) -> Dict[Location, yaml.Mark]:
    """Map the location of every mapping key and sequence item to its source mark."""
    marks: Dict[Location, yaml.Mark] = {}
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            child = (*location, str(key_node.value))
            marks.update(_source_marks(value_node, child))
            marks[child] = key_node.start_mark
    elif isinstance(node, yaml.SequenceNode):
        for index, item_node in enumerate(node.value):
            child = (*location, index)
            marks.update(_source_marks(item_node, child))
            marks[child] = item_node.start_mark
    return marks


def _find_mark(
    marks: Dict[Location, yaml.Mark], location: Location
) -> Optional[yaml.Mark]:
    """Find the source mark for a location, falling back to its closest parent.

    Missing fields (e.g. ``inputs[0].uri``) are reported at their parent item.
    """
    while location:
        if location in marks:
            return marks[location]
        location = location[:-1]
    return None


def _expand_path(path: Path, base_path: Path) -> Path:
    os.environ["MANIFEST_DIR"] = str(base_path)
    path = Path(os.path.expandvars(str(path))).expanduser()
    if not path.is_absolute():
        if not base_path.is_absolute():
            raise ValueError("base_path must be absolute")
        return base_path / path
    else:
        path = path.resolve()
    return path


ManifestUrl = Annotated[SimDBUrl, UrlConstraints(allowed_schemes=["file", "imas"])]


class DataType(Enum):
    UNKNOWN = auto()
    UUID = auto()
    FILE = auto()
    IMAS = auto()


def _get_data_object_type(uri: SimDBUrl) -> "DataType":
    if uri.scheme == "imas":
        return DataType.IMAS
    elif uri.scheme == "file":
        if uri.path is None:
            raise ValueError("no path provided")
        if Path(uri.path).suffix == ".nc":
            with Dataset(uri.path, "r") as ds:
                if getattr(ds, "Conventions", None) == "IMAS":
                    return DataType.IMAS
        return DataType.FILE

    raise ValueError(f"URI scheme ({uri.scheme}:) not recognized")


class DataObject(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    uri: ManifestUrl = Field()

    _type: DataType = PrivateAttr(default=DataType.UNKNOWN)

    @model_validator(mode="after")
    def _resolve_type(self) -> "DataObject":
        self._type = _get_data_object_type(self.uri)
        return self

    @property
    def name(self) -> str:
        return self.uri.encoded_string()

    @field_validator("uri", mode="after")
    @classmethod
    def validate_uri(cls, v: ManifestUrl, info):
        context = info.context or {}
        base_path = context.get("base_path")
        if not base_path:
            base_path = Path.cwd()

        if v.path is None:
            raise ValueError("no uri path provided")

        if v.scheme == "imas":
            qs = dict(v.query_params())
            if "path" not in qs and (
                "shot" not in qs or "run" not in qs or "database" not in qs
            ):
                raise ValueError(
                    "no path or (shot, run, database) provided in IMAS uri"
                )

        elif v.scheme == "file":
            v = v.build(
                scheme="file",
                path=_expand_path(Path(v.path), base_path).as_posix(),
            )

        return v

    @property
    def type(self):
        return self._type


class Source(DataObject):
    pass


class Sink(DataObject):
    pass


def _validate_metadata_name(name: str) -> None:
    forbidden_characters = {":", "=", "#"}
    bad_chars = set(name).intersection(forbidden_characters)
    if bad_chars:
        raise ValueError(
            f"invalid metadata field name {name} - "
            f"contains forbidden character(s): {', '.join(bad_chars)}"
        )


def _validate_metadata_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if len(item) != 1:
        raise ValueError("metadata values should be a name value pair")
    _validate_metadata_name(next(iter(item)))
    return item


# Validated per item so that errors point at the offending metadata entry.
MetadataItem = Annotated[Dict[str, Any], AfterValidator(_validate_metadata_item)]


class MetadataEntryV1(BaseModel):
    """A version 1 metadata entry: ``{"values": {name: value, ...}}``."""

    values: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("values")
    @classmethod
    def validate_names(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        for name in values:
            _validate_metadata_name(name)
        return values


class _ManifestBase(BaseModel):
    """Fields shared by all manifest versions."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    alias: Optional[str] = None
    responsible_name: Optional[str] = None
    inputs_raw: List[Source] = Field(default_factory=list, alias="inputs")
    outputs_raw: List[Sink] = Field(default_factory=list, alias="outputs")

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and urllib.parse.quote(v) != v:
            raise ValueError(f"illegal characters in alias: {v}")
        return v

    @field_validator("inputs_raw", "outputs_raw")
    @classmethod
    def validate_uris(cls, v: List[DataObject], info) -> List[DataObject]:
        seen_uris = set()
        for item in v:
            uri_str = item.name
            if uri_str in seen_uris:
                raise ValueError(
                    "Duplicate URI found in "
                    f"{info.field_name.replace('_raw', '')}: {uri_str}"
                )
            seen_uris.add(uri_str)
        return v


class ManifestV1(_ManifestBase):
    """Manifest schema for version 1.

    Only kept around to load legacy manifests and convert them to the current
    (version 2) format via :meth:`to_v2_data`. It is validated in full against
    the file's own layout, so errors point at the file as written; only the
    metadata layout differs between versions.
    """

    manifest_version: Literal[1] = Field(default=1)
    metadata: List[MetadataEntryV1] = Field(default_factory=list)

    def to_v2_data(self) -> Dict[str, Any]:
        """Return the manifest as version 2 data ready for ``Manifest``.

        Version 1 stores metadata as a list of ``{"values": {name: value, ...}}``
        entries, whereas version 2 expects a list of single ``{name: value}`` pairs.
        """
        data: Dict[str, Any] = {
            "manifest_version": 2,
            "inputs": self.inputs_raw,
            "outputs": self.outputs_raw,
            "metadata": [
                {name: value}
                for entry in self.metadata
                for name, value in entry.values.items()
            ],
        }
        if self.alias is not None:
            data["alias"] = self.alias
        if self.responsible_name is not None:
            data["responsible_name"] = self.responsible_name
        return data


class Manifest(_ManifestBase):
    manifest_version: Literal[2] = Field(default=2)
    metadata_raw: List[MetadataItem] = Field(default_factory=list, alias="metadata")

    _path: Path = PrivateAttr(default_factory=Path)
    _inputs: List[Source] = PrivateAttr(default_factory=list)
    _outputs: List[Sink] = PrivateAttr(default_factory=list)
    _metadata: Dict[str, Any] = PrivateAttr(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def check_deprecated_version(cls, data: Any, info) -> Any:
        if not isinstance(data, dict):
            return data

        if "version" in data:
            warnings.warn(
                "The 'version' field is deprecated and will be removed "
                "in a future version. Please use 'manifest_version' instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            if "manifest_version" not in data:
                data["manifest_version"] = data.pop("version")

        # Accept legacy version 1 manifests by upgrading them to version 2.
        if data.get("manifest_version") == 1:
            warnings.warn(
                "Manifest version 1 is deprecated and will be removed in a "
                "future version. It has been converted to version 2 in memory; "
                "please update the manifest to version 2.",
                DeprecationWarning,
                stacklevel=3,
            )
            data = ManifestV1.model_validate(data, context=info.context).to_v2_data()

        return data

    @model_validator(mode="after")
    def resolve_metadata(self, info) -> "Manifest":
        for metadata_item in self.metadata_raw:
            self._metadata.update(metadata_item)
        return self

    def _resolve_manifest_items(self, items, factory_cls, skip_glob_check):
        resolved = []
        for item in items:
            if item.type == DataType.FILE and item.uri.path:
                path_obj = Path(item.uri.path)

                matches = list(path_obj.parent.glob(path_obj.name))

                if not matches and skip_glob_check:
                    matches = [path_obj]

                if not matches:
                    raise ValueError(f"No files found matching path {path_obj}")

                for p in matches:
                    resolved.append(
                        factory_cls(
                            uri=SimDBUrl.build(scheme="file", path=p.as_posix())
                        )
                    )
            else:
                resolved.append(item)
        return resolved

    @model_validator(mode="after")
    def resolve_inputs_and_outputs(self, info) -> "Manifest":
        context = info.context or {}
        skip_glob_check = context.get("skip_glob_check", False)

        context.setdefault(
            "base_path",
            self._path.absolute().parent if self._path != Path() else Path.cwd(),
        )

        self._inputs = self._resolve_manifest_items(
            self.inputs_raw, Source, skip_glob_check
        )
        self._outputs = self._resolve_manifest_items(
            self.outputs_raw, Sink, skip_glob_check
        )

        return self

    @classmethod
    def _get_loader(cls):
        def ndarray_constructor(
            loader: yaml.SafeLoader, node: yaml.nodes.MappingNode
        ) -> np.ndarray:
            mapping = loader.construct_mapping(node, deep=True)
            if "data" not in mapping:
                raise yaml.constructor.ConstructorError(
                    None, None, "!ndarray requires a 'data' entry", node.start_mark
                )
            try:
                return np.array(mapping["data"], mapping.get("dtype", None))
            except (TypeError, ValueError) as err:
                raise yaml.constructor.ConstructorError(
                    None, None, f"invalid !ndarray: {err}", node.start_mark
                ) from err

        loader = yaml.SafeLoader
        loader.add_constructor("!ndarray", ndarray_constructor)
        return loader

    @classmethod
    def _read_yaml(
        cls, file_path: Path
    ) -> Tuple[Dict[str, Any], Dict[Location, yaml.Mark]]:
        """Read a YAML file, returning its data and the source mark of each item."""
        with file_path.open() as file:
            loader = cls._get_loader()(file)
            try:
                node = loader.get_single_node()
                data = loader.construct_document(node) if node is not None else None
            except yaml.YAMLError as err:
                raise InvalidManifestError.from_yaml_error(file_path, err) from err
            finally:
                loader.dispose()
        if node is None:
            raise InvalidManifestError(file_path, [ManifestIssue("manifest is empty")])
        if not isinstance(data, dict):
            message = "manifest should be a mapping, e.g. 'manifest_version: 2'"
            raise InvalidManifestError(
                file_path, [ManifestIssue.at(message, node.start_mark)]
            )
        return data, _source_marks(node)

    @classmethod
    def from_template(cls) -> "Manifest":
        dir_path = Path(__file__).resolve().parent
        raw_data, _ = cls._read_yaml(dir_path / "template.yaml")

        model = cls.model_validate(raw_data, context={"skip_glob_check": True})
        model._path = dir_path / "template.yaml"
        return model

    @classmethod
    def load_from_file(
        cls, file_path: Path, overrides: Optional[dict] = None
    ) -> "Manifest":
        raw_data, marks = cls._read_yaml(file_path)
        overrides = overrides or {}
        raw_data.update(overrides)

        try:
            model = cls.model_validate(
                raw_data, context={"base_path": file_path.absolute().parent}
            )
        except ValidationError as err:
            raise InvalidManifestError.from_validation_error(
                file_path, err, marks, overridden=overrides
            ) from err
        model._path = file_path
        return model

    def save(self, out_file: TextIO) -> None:
        yaml.dump(
            self.model_dump(mode="json", by_alias=True, exclude_none=True),
            out_file,
            default_flow_style=False,
        )

    @property
    def version(self) -> int:
        return self.manifest_version

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._metadata

    @property
    def inputs(self) -> Iterable[Source]:
        return self._inputs

    @property
    def outputs(self) -> Iterable[Sink]:
        return self._outputs
