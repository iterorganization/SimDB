from enum import Enum
import uuid
import sys
from collections.abc import Iterable
from datetime import datetime
from typing import List, Union, Dict, Any, TYPE_CHECKING, Optional
from getpass import getuser

import numpy as np
from sqlalchemy import Column, types as sql_types, Table, ForeignKey
from sqlalchemy.orm import relationship

from .utils import flatten_dict, unflatten_dict, checked_get
from .types import UUID
from .base import Base
from .file import File
from ...cli.manifest import Manifest, DataObject
from ...docstrings import inherit_docstrings
from ...config.config import Config


if TYPE_CHECKING or 'sphinx' in sys.modules:
    # Only importing these for type checking and documentation generation in order to speed up runtime startup.
    from .metadata import MetaData


simulation_input_files = Table("simulation_input_files", Base.metadata,
                               Column("simulation_id", sql_types.Integer, ForeignKey("simulations.id")),
                               Column("file_id", sql_types.Integer, ForeignKey("files.id")))


simulation_output_files = Table("simulation_output_files", Base.metadata,
                                Column("simulation_id", sql_types.Integer, ForeignKey("simulations.id")),
                                Column("file_id", sql_types.Integer, ForeignKey("files.id")))


simulation_watchers = Table("simulation_watchers", Base.metadata,
                            Column("simulation_id", sql_types.Integer, ForeignKey("simulations.id")),
                            Column("watcher_id", sql_types.Integer, ForeignKey("watchers.id")))


@inherit_docstrings
class Simulation(Base):
    """
    Class to represent simulations in the database ORM.
    """
    class Status(Enum):
        INVALIDATED = 'invalidated'
        ACCEPTED = 'accepted'
        FAILED = 'failed'
        PASSED = 'passed'
        DEPRECATED = 'deprecated'

    __tablename__ = "simulations"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False, unique=True)
    alias: str = Column(sql_types.String(250), nullable=True, unique=True)
    inputs: List["File"] = relationship("File", secondary=simulation_input_files)
    outputs: List["File"] = relationship("File", secondary=simulation_output_files)
    meta: List["MetaData"] = relationship("MetaData")
    watchers = relationship("Watcher", secondary=simulation_watchers, lazy='dynamic')

    def __init__(self, manifest: Union[Manifest, None], config: Optional[Config]=None) -> None:
        """
        Initialise a new Simulation object using the provided Manifest.

        :param manifest: The Manifest to load the data from, or None to create an empty Simulation.
        """
        from .metadata import MetaData

        if manifest is None:
            return
        self.uuid = uuid.uuid1()
        self.datetime = datetime.now()
        self.status = Simulation.Status.INVALIDATED
        self.user = getuser()

        if manifest.alias:
            self.alias = manifest.alias

        for input in manifest.inputs:
            self.inputs.append(File(input.type, input.uri, config=config))

        for output in manifest.outputs:
            self.outputs.append(File(output.type, output.uri, config=config))
            if output.type == DataObject.Type.IMAS:
                from ...imas.utils import open_imas, list_idss, check_time
                from ...imas.metadata import load_metadata
                entry = open_imas(output.uri)
                idss = list_idss(entry)
                for ids in idss:
                    check_time(entry, ids)

                self.meta.append(MetaData('ids', '[%s]' % ', '.join(idss)))

                meta = load_metadata(entry)
                flattened_meta: Dict[str, str] = {}
                flatten_dict(flattened_meta, meta)

                for key, value in flattened_meta.items():
                    self.meta.append(MetaData(key, value))

        flattened_dict: Dict[str, str] = {}
        flatten_dict(flattened_dict, manifest.metadata)

        for key, value in flattened_dict.items():
            self.meta.append(MetaData(key, value))

        if not self.find_meta("status"):
            self.set_meta("status", Simulation.Status.INVALIDATED.value)

    def __str__(self):
        result = ""
        for name in ("uuid", "alias"):
            result += "%s:%s%s\n" % (name, ((10 - len(name)) * " "), getattr(self, name))
        result += "metadata:\n"
        for meta in self.meta:
            if isinstance(meta.value, Iterable) and '\n' in meta.value:
                first_line = True
                for line in meta.value.split('\n'):
                    if first_line:
                        result += f"  {meta.element}: {line}\n"
                    elif line:
                        indent = ' ' * (len(meta.element) + 2)
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

    def set_meta(self, name: str, value: str) -> None:
        from .metadata import MetaData

        for m in self.meta:
            if m.element == name:
                m.value = value
                break
        else:
            self.meta.append(MetaData(name, value))

    @classmethod
    def from_data(cls, data: Dict[str, Union[str, Dict, List]]) -> "Simulation":
        from .metadata import MetaData
        simulation = Simulation(None)
        simulation.uuid = uuid.UUID(checked_get(data, "uuid", str))
        simulation.alias = checked_get(data, "alias", str)
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

    def data(self, recurse: bool=False) -> Dict[str, Union[str, List]]:
        data = dict(
            uuid=self.uuid.hex,
            alias=self.alias,
        )
        if recurse:
            data["inputs"] = [f.data(recurse=True) for f in self.inputs]
            data["outputs"] = [f.data(recurse=True) for f in self.outputs]
            data["metadata"] = [m.data(recurse=True) for m in self.meta]
        return data

    def meta_dict(self) -> Dict[str, Union[Dict, Any]]:
        meta = {m.element: m.value for m in self.meta}
        return unflatten_dict(meta)
