import itertools
import sys
import uuid
from datetime import datetime as dt
from enum import Enum
from getpass import getuser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from simdb.enums import IngestionStatus
from simdb.imas.utils import SimDBUrl
from simdb.remote.models import (
    FileDataList,
    MetadataData,
    MetadataDataList,
    SimulationData,
    SimulationDataResponse,
    SimulationTraceData,
)

if sys.version_info < (3, 11):
    from backports.datetime_fromisoformat import MonkeyPatch

from dateutil import parser as date_parser
from sqlalchemy import JSON, Column, ForeignKey, Table, text
from sqlalchemy import types as sql_types
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship

if "sphinx" in sys.modules:
    # Patch to allow sphix doc generation
    from sqlalchemy.sql.elements import ClauseElement

    ClauseElement.__bool__ = lambda self: True  # type: ignore


from simdb.cli.manifest import DataObject, DataType, Manifest
from simdb.config.config import Config
from simdb.docstrings import inherit_docstrings
from simdb.imas.metadata import load_metadata
from simdb.imas.utils import (
    check_time,
    extract_ids_occurrence,
    get_path_for_legacy_uri,
    is_legacy_imas_uri,
    list_idss,
    open_imas,
)

from .base import Base
from .file import File
from .types import UUID
from .utils import checked_get, flatten_dict, unflatten_dict
from .watcher import Watcher

if sys.version_info < (3, 11):
    MonkeyPatch.patch_fromisoformat()


simulation_input_files = Table(
    "simulation_input_files",
    Base.metadata,
    Column("simulation_id", sql_types.Integer, ForeignKey("simulations.id")),
    Column("file_id", sql_types.Integer, ForeignKey("files.id")),
)

simulation_output_files = Table(
    "simulation_output_files",
    Base.metadata,
    Column("simulation_id", sql_types.Integer, ForeignKey("simulations.id")),
    Column("file_id", sql_types.Integer, ForeignKey("files.id")),
)

simulation_watchers = Table(
    "simulation_watchers",
    Base.metadata,
    Column("simulation_id", sql_types.Integer, ForeignKey("simulations.id")),
    Column("watcher_id", sql_types.Integer, ForeignKey("watchers.id")),
)


def _update_legacy_uri(data_object: DataObject):
    path = get_path_for_legacy_uri(data_object.uri)
    qs = dict(data_object.uri.query_params())
    backend = qs.get("backend", "hdf5")
    return SimDBUrl.build(scheme="imas", path=backend, query=f"path={path}")


class MetaDataWrapper:
    """Temporary wrapper to provide backwards compatibility with MetaData interface."""

    def __init__(self, element: str, value: Any):
        self.element = element
        self.value = value

    def data(self, recurse: bool = False) -> Dict[str, Any]:
        return {"element": self.element, "value": self.value}

    def to_model(self) -> "MetadataData":
        return MetadataData(element=self.element, value=self.value)


@inherit_docstrings
class Simulation(Base):
    """
    Class to represent simulations in the database ORM.
    """

    class Status(Enum):
        NOT_VALIDATED = "not validated"
        ACCEPTED = "accepted"
        FAILED = "failed"
        PASSED = "passed"
        DEPRECATED = "deprecated"
        DELETED = "deleted"

    __tablename__ = "simulations"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False, unique=True, index=True)
    alias = Column(sql_types.String(250), nullable=True, unique=True, index=True)
    datetime = Column(sql_types.DateTime, nullable=False)
    _metadata = Column(
        "metadata",
        MutableDict.as_mutable(
            postgresql.JSONB(astext_type=sql_types.Text()).with_variant(
                JSON(), "sqlite"
            )
        ),
        nullable=True,
        default=dict,
    )
    inputs: List["File"] = relationship(
        "File", secondary=simulation_input_files, backref="input_for"
    )
    outputs: List["File"] = relationship(
        "File", secondary=simulation_output_files, backref="output_of"
    )
    watchers: List["Watcher"] = relationship(
        "Watcher", secondary=simulation_watchers, lazy="dynamic"
    )

    ingestion_status = Column(
        sql_types.Enum(IngestionStatus),
        nullable=False,
        default=IngestionStatus.COMPLETED,
    )
    # Set on insert and refreshed on every update, so the stale-ingestion sweep
    # can tell how long a simulation has been sitting in its current status.
    ingestion_status_updated_at = Column(
        sql_types.DateTime,
        nullable=False,
        default=dt.now,
        onupdate=dt.now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    ingestion_version = Column(sql_types.Integer, nullable=False, default=0)

    @property
    def meta(self) -> List[MetaDataWrapper]:
        """
        Property to provide backwards compatibility.
        Returns a list of MetaDataWrapper objects from the JSON metadata.
        """
        meta_dict = self._get_metadata_dict()
        return [MetaDataWrapper(k, v) for k, v in meta_dict.items()]

    def _get_metadata_dict(self) -> Dict[str, Any]:
        if self._metadata is None:
            return {}
        return self._metadata

    def _set_metadata_dict(self, meta_dict: Dict[str, Any]) -> None:
        self._metadata = meta_dict

    def __init__(
        self, manifest: Union[Manifest, None], config: Optional[Config] = None
    ) -> None:
        """
        Initialise a new Simulation object using the provided Manifest.

        :param manifest: The Manifest to load the data from, or None to create an empty
                         Simulation.
        """

        if manifest is None:
            self._metadata = {}
            return
        self.uuid = uuid.uuid1()
        self.datetime = dt.now()
        self._metadata = {}

        # For legacy simulation import responsible_name is from manifest else it will be
        # the user.email
        if manifest.responsible_name:
            self.set_meta("uploaded_by", manifest.responsible_name)

        self.user = getuser()

        if manifest.alias:
            self.alias = manifest.alias

        all_input_idss = []

        for input in manifest.inputs:
            if input.type == DataType.IMAS:
                entry = open_imas(input.uri)
                idss = list_idss(entry)

                for ids in idss:
                    ids_name, occurrence = extract_ids_occurrence(ids)
                    check_time(entry, ids_name, occurrence)

                all_input_idss += idss

                entry.close()

            file = File(input.type, input.uri, all_input_idss, config=config)
            if input.type == DataType.IMAS and is_legacy_imas_uri(input.uri):
                file.uri = _update_legacy_uri(input)
            self.inputs.append(file)

        if all_input_idss:
            self.set_meta("input_ids", "[{}]".format(", ".join(all_input_idss)))

        all_output_idss = []

        for output in manifest.outputs:
            if output.type == DataType.IMAS:
                entry = open_imas(output.uri)
                idss = list_idss(entry)
                for ids in idss:
                    ids_name, occurrence = extract_ids_occurrence(ids)
                    check_time(entry, ids_name, occurrence)

                all_output_idss += idss

                meta = load_metadata(entry)
                entry.close()
                flattened_meta = flatten_dict(meta)

                for key, value in flattened_meta.items():
                    self.set_meta(key, value)

            file = File(output.type, output.uri, all_output_idss, config=config)
            if output.type == DataType.IMAS and is_legacy_imas_uri(output.uri):
                file.uri = _update_legacy_uri(output)

            self.outputs.append(file)

        if all_output_idss:
            self.set_meta("ids", "[{}]".format(", ".join(all_output_idss)))

        flattened_dict = flatten_dict(manifest.metadata)

        for key, value in flattened_dict.items():
            self.set_meta(key, value)
        if not self.find_meta("status"):
            self.set_meta("status", Simulation.Status.NOT_VALIDATED.value)
        self.validate_meta()

    @property
    def status(self) -> Optional["Simulation.Status"]:
        result = self.find_meta("status")
        if result:
            value = result[0] if result[0] != "invalidated" else "not validated"
            return Simulation.Status(value)
        return None

    @status.setter
    def status(self, status: "Simulation.Status"):
        self.set_meta("status", status.value)

    def __str__(self):
        result = ""
        for name in ("uuid", "alias"):
            result += "{}:{}{}\n".format(
                name,
                ((10 - len(name)) * " "),
                getattr(self, name),
            )
        result += "metadata:\n"
        meta_dict = self._get_metadata_dict()
        for element, value in meta_dict.items():
            if isinstance(value, str) and "\n" in value:
                first_line = True
                for line in value.split("\n"):
                    if first_line:
                        result += f"  {element}: {line}\n"
                    elif line:
                        indent = " " * (len(element) + 2)
                        result += f"  {indent}{line}"
                    first_line = False
            elif isinstance(value, dict) and "min" in value and "max" in value:
                result += f"  {element}: [{value['min']}, {value['max']}]\n"
            else:
                result += f"  {element}: {value}\n"
        result += "inputs:\n"
        for file in self.inputs:
            result += f"{file}\n"
        result += "outputs:\n"
        for file in self.outputs:
            result += f"{file}\n"
        return result

    def find_meta(self, name: str) -> List[Any]:
        meta_dict = self._get_metadata_dict()
        if name in meta_dict:
            return [meta_dict[name]]
        return []

    def remove_meta(self, name: str) -> None:
        if self._metadata is None:
            return
        if name in self._metadata:
            del self._metadata[name]

    def set_meta(self, name: str, value: Any) -> None:
        if self._metadata is None:
            self._metadata = {}
        self._metadata[name] = value

    def validate_meta(self) -> None:
        """
        Check the metadata elements for duplicates, throwing an exception if found.

        With JSON storage, duplicates are not possible by design (dict keys are unique),
        but we keep this method for backwards compatibility.
        """
        # With JSON/dict storage, duplicates are impossible
        pass

    def file_paths(self) -> Set[Path]:
        def _get_path(file: File) -> Optional[Path]:
            if file.uri.scheme == "file":
                if file.type == DataType.FILE:
                    if file.uri.path is None:
                        raise ValueError("Data object path is not set")
                    return Path(file.uri.path)
                elif file.type == DataType.IMAS:
                    if file.uri.path is None:
                        raise ValueError("Data object path is not set")
                    return Path(file.uri.path).parent
                else:
                    raise ValueError(f"Unknown file type {file.type}")
            elif file.uri.scheme == "imas":
                qs = dict(file.uri.query_params())
                return Path(qs["path"]) if "path" in qs else None
            return None

        file_paths = set()
        for f in itertools.chain(self.inputs, self.outputs):
            path = _get_path(f)
            if path is not None:
                file_paths.add(path)
        return file_paths

    @classmethod
    def from_data(cls, data: Dict[str, Union[str, Dict, List]]) -> "Simulation":
        simulation = Simulation(None)
        simulation.uuid = checked_get(data, "uuid", uuid.UUID)
        simulation.alias = checked_get(data, "alias", str)
        if "datetime" not in data:
            data["datetime"] = dt.now().isoformat()
        simulation.datetime = date_parser.parse(checked_get(data, "datetime", str))
        if "inputs" in data:
            inputs = checked_get(data, "inputs", list)
            simulation.inputs = [File.from_data(el) for el in inputs]
        if "outputs" in data:
            outputs = checked_get(data, "outputs", list)
            simulation.outputs = [File.from_data(el) for el in outputs]
        if "metadata" in data:
            metadata = checked_get(data, "metadata", list)
            meta_dict = {}
            for el in metadata:
                if not isinstance(el, dict):
                    raise Exception("corrupted metadata element - expected dictionary")
                if "element" in el and "value" in el:
                    meta_dict[el["element"]] = el["value"]
            simulation._set_metadata_dict(meta_dict)
        return simulation

    @classmethod
    def from_data_model(cls, data: SimulationData) -> "Simulation":
        simulation = Simulation(None)
        simulation.uuid = data.uuid
        simulation.alias = data.alias
        simulation.datetime = data.datetime
        simulation.inputs = [File.from_data_model(el) for el in data.inputs.root]
        simulation.outputs = [File.from_data_model(el) for el in data.outputs.root]
        simulation._set_metadata_dict(
            {el.element: el.value for el in data.metadata.root}
        )
        return simulation

    def data(
        self,
        recurse: bool = False,
        meta_keys: Optional[List[str]] = None,
        no_meta: bool = False,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "uuid": self.uuid,
            "alias": self.alias,
            "datetime": self.datetime.isoformat(),
        }
        if recurse:
            data["inputs"] = [f.data(recurse=True) for f in self.inputs]
            data["outputs"] = [f.data(recurse=True) for f in self.outputs]
            if not no_meta:
                meta_dict = self._get_metadata_dict()
                data["metadata"] = [
                    {"element": k, "value": v} for k, v in meta_dict.items()
                ]
        elif meta_keys:
            meta_dict = self._get_metadata_dict()
            data["metadata"] = [
                {"element": k, "value": v}
                for k, v in meta_dict.items()
                if k in meta_keys
            ]
        return data

    def to_model(
        self, recurse: bool = False, meta_keys: Optional[List[str]] = None
    ) -> SimulationData:
        inputs = FileDataList()
        outputs = FileDataList()
        metadata = MetadataDataList()
        if recurse:
            inputs = FileDataList([f.to_model() for f in self.inputs])
            outputs = FileDataList([f.to_model() for f in self.outputs])
            metadata = MetadataDataList([m.to_model() for m in self.meta])
        elif meta_keys:
            metadata = MetadataDataList(
                [m.to_model() for m in self.meta if m.element in meta_keys]
            )
        return SimulationData(
            uuid=self.uuid,
            alias=self.alias,
            datetime=self.datetime,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
        )

    def to_model_with_refs(
        self, recurse: bool = False, meta_keys: Optional[List[str]] = None
    ) -> SimulationDataResponse:
        inputs = FileDataList()
        outputs = FileDataList()
        metadata = MetadataDataList()
        if recurse:
            inputs = FileDataList([f.to_model() for f in self.inputs])
            outputs = FileDataList([f.to_model() for f in self.outputs])
            metadata = MetadataDataList([m.to_model() for m in self.meta])
        elif meta_keys:
            metadata = MetadataDataList(
                [m.to_model() for m in self.meta if m.element in meta_keys]
            )
        return SimulationDataResponse(
            uuid=self.uuid,
            alias=self.alias,
            datetime=self.datetime,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
            parents=[],
            children=[],
        )

    def to_model_trace(
        self, recurse: bool = False, meta_keys: Optional[List[str]] = None
    ) -> SimulationTraceData:
        inputs = FileDataList()
        outputs = FileDataList()
        metadata = MetadataDataList()
        if recurse:
            inputs = FileDataList([f.to_model() for f in self.inputs])
            outputs = FileDataList([f.to_model() for f in self.outputs])
            metadata = MetadataDataList([m.to_model() for m in self.meta])
        elif meta_keys:
            metadata = MetadataDataList(
                [m.to_model() for m in self.meta if m.element in meta_keys]
            )
        return SimulationTraceData(
            uuid=self.uuid,
            alias=self.alias,
            datetime=self.datetime,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
        )

    def meta_dict(self) -> Dict[str, Union[Dict, Any]]:
        meta = self._get_metadata_dict()
        return unflatten_dict(meta)
