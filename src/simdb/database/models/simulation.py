from enum import Enum
import uuid
import sys
from collections.abc import Iterable
from collections import defaultdict
from datetime import datetime
from typing import List, Union, Dict, Any, TYPE_CHECKING, Optional
from getpass import getuser

if sys.version_info < (3, 11):
    from backports.datetime_fromisoformat import MonkeyPatch

from sqlalchemy.orm import relationship
from sqlalchemy import Table, ForeignKey, Column, types as sql_types

if "sphinx" in sys.modules:
    # Patch to allow sphix doc generation
    from sqlalchemy.sql.elements import ClauseElement

    ClauseElement.__bool__ = lambda self: True

from .utils import flatten_dict, unflatten_dict, checked_get
from .types import UUID
from .base import Base
from .file import File
from ...cli.manifest import Manifest, DataObject
from ...docstrings import inherit_docstrings
from ...config.config import Config


if sys.version_info < (3, 11):
    MonkeyPatch.patch_fromisoformat()


if TYPE_CHECKING:
    # Only importing these for type checking and documentation generation in order to speed up runtime startup.
    from .metadata import MetaData
    from .watcher import Watcher

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
    alias: str = Column(sql_types.String(250), nullable=True, unique=True, index=True)
    datetime: datetime = Column(sql_types.DateTime, nullable=False)
    inputs: List["File"] = relationship(
        "File", secondary=simulation_input_files, backref="input_for"
    )
    outputs: List["File"] = relationship(
        "File", secondary=simulation_output_files, backref="output_of"
    )
    meta: List["MetaData"] = relationship(
        "MetaData", lazy="raise", cascade="all, delete-orphan"
    )
    watchers: List["Watcher"] = relationship(
        "Watcher", secondary=simulation_watchers, lazy="dynamic"
    )

    def __init__(
        self, manifest: Union[Manifest, None], config: Optional[Config] = None
    ) -> None:
        """
        Initialise a new Simulation object using the provided Manifest.

        :param manifest: The Manifest to load the data from, or None to create an empty Simulation.
        """
        from .metadata import MetaData

        if manifest is None:
            return
        self.uuid = uuid.uuid1()
        self.datetime = datetime.now()
        # self.status = Simulation.Status.NOT_VALIDATED
        self.user = getuser()

        if manifest.alias:
            self.alias = manifest.alias

        for input in manifest.inputs:
            self.inputs.append(File(input.type, input.uri, config=config))

        all_idss = []

        for output in manifest.outputs:
            self.outputs.append(File(output.type, output.uri, config=config))
            if output.type == DataObject.Type.IMAS:
                from ...imas.utils import open_imas, list_idss, check_time
                from ...imas.metadata import load_metadata

                entry = open_imas(output.uri)
                idss = list_idss(entry)
                for ids in idss:
                    check_time(entry, ids)

                all_idss += idss

                meta = load_metadata(entry)
                flattened_meta: Dict[str, str] = {}
                flatten_dict(flattened_meta, meta)

                for key, value in flattened_meta.items():
                    self.meta.append(MetaData(key, value))

        if all_idss:
            self.meta.append(MetaData("ids", "[%s]" % ", ".join(all_idss)))

        flattened_dict: Dict[str, str] = {}
        flatten_dict(flattened_dict, manifest.metadata)

        for key, value in flattened_dict.items():
            self.set_meta(key, value)

        if not self.find_meta("status"):
            self.set_meta("status", Simulation.Status.NOT_VALIDATED.value)

        self.validate_meta()

    @property
    def status(self) -> Optional["Simulation.Status"]:
        result = self.find_meta("status")
        if result:
            value = (
                result[0].value if result[0].value != "invalidated" else "not validated"
            )
            return Simulation.Status(value)
        return None

    @status.setter
    def status(self, status: "Simulation.Status"):
        self.set_meta("status", status.value)

    def __str__(self):
        import numpy as np

        result = ""
        for name in ("uuid", "alias"):
            result += "%s:%s%s\n" % (
                name,
                ((10 - len(name)) * " "),
                getattr(self, name),
            )
        result += "metadata:\n"
        for meta in self.meta:
            if (
                isinstance(meta.value, Iterable)
                and not isinstance(meta.value, np.ndarray)
                and "\n" in meta.value
            ):
                first_line = True
                for line in meta.value.split("\n"):
                    if first_line:
                        result += f"  {meta.element}: {line}\n"
                    elif line:
                        indent = " " * (len(meta.element) + 2)
                        result += f"  {indent}{line}"
                    first_line = False
            elif isinstance(meta.value, np.ndarray):
                string = np.array2string(meta.value, threshold=10)
                result += f"  {meta.element}: {string}\n"
            else:
                result += f"  {meta.element}: {meta.value}\n"
        result += "inputs:\n"
        for file in self.inputs:
            result += f"{file}\n"
        result += "outputs:\n"
        for file in self.outputs:
            result += f"{file}\n"
        return result

    def find_meta(self, name: str) -> List["MetaData"]:
        return [m for m in self.meta if m.element == name]

    def remove_meta(self, name: str) -> None:
        self.meta = [m for m in self.meta if m.element != name]

    def set_meta(self, name: str, value: str) -> None:
        from .metadata import MetaData

        for m in self.meta:
            if m.element == name:
                m.value = value
                break
        else:
            self.meta.append(MetaData(name, value))

    def validate_meta(self) -> None:
        """
        Check the metadata elements for duplicates, throwing and exception if found.

        Duplicates should not be possible but if there is an issue causing them to arise then at least it will be
        caught early rather than causing an SQL constraint failure later.
        """
        names = [m.element for m in self.meta]
        counts = defaultdict(lambda: 0)
        for name in names:
            counts[name] += 1
        duplicates = [k for (k, v) in counts.items() if v > 1]
        if len(duplicates) > 0:
            raise ValueError(
                f"Duplicate metadata elements {duplicates} found for simulation {self.uuid}"
            )

    @classmethod
    def from_data(cls, data: Dict[str, Union[str, Dict, List]]) -> "Simulation":
        from .metadata import MetaData

        simulation = Simulation(None)
        simulation.uuid = checked_get(data, "uuid", uuid.UUID)
        simulation.alias = checked_get(data, "alias", str)
        if "datetime" not in data:
            data["datetime"] = datetime.now().isoformat()
        simulation.datetime = datetime.fromisoformat(checked_get(data, "datetime", str))
        if "inputs" in data:
            inputs = checked_get(data, "inputs", list)
            simulation.inputs = [File.from_data(el) for el in inputs]
        if "outputs" in data:
            outputs = checked_get(data, "outputs", list)
            simulation.outputs = [File.from_data(el) for el in outputs]
        if "metadata" in data:
            metadata = checked_get(data, "metadata", list)
            for el in metadata:
                if not isinstance(el, dict):
                    raise Exception("corrupted metadata element - expected dictionary")
                simulation.meta.append(MetaData.from_data(el))
        return simulation

    def data(
        self, recurse: bool = False, meta_keys: Optional[List[str]] = None
    ) -> Dict[str, Union[str, List]]:
        data = dict(
            uuid=self.uuid,
            alias=self.alias,
            datetime=self.datetime.isoformat(),
        )
        if recurse:
            data["inputs"] = [f.data(recurse=True) for f in self.inputs]
            data["outputs"] = [f.data(recurse=True) for f in self.outputs]
            data["metadata"] = [m.data(recurse=True) for m in self.meta]
        elif meta_keys:
            data["metadata"] = [
                m.data(recurse=True) for m in self.meta if m.element in meta_keys
            ]
        return data

    def meta_dict(self) -> Dict[str, Union[Dict, Any]]:
        meta = {m.element: m.value for m in self.meta}
        return unflatten_dict(meta)
