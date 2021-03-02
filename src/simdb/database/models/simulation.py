import re
import uuid
from datetime import datetime
from itertools import chain
from typing import List, Union, Dict, Any, Type

from dateutil import parser as date_parser
from sqlalchemy import Column, types as sql_types, Table, ForeignKey
from sqlalchemy.orm import relationship

from ._base import _flatten_dict
from .types import UUID
from . import Base, MetaData, File
from ...cli.manifest import Manifest, DataObject
from ...docstrings import inherit_docstrings


def _checked_get(data: Dict[str, Any], key, type: Type):
    if not isinstance(data[key], type):
        raise ValueError("corrupted %s - expected %s" % (key, str(type)))
    return data[key]


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
    __tablename__ = "simulations"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False, unique=True)
    alias = Column(sql_types.String(250), nullable=True, unique=True)
    datetime = Column(sql_types.DateTime, nullable=False)
    status = Column(sql_types.String(20), nullable=False)
    inputs: List["File"] = relationship("File", secondary=simulation_input_files)
    outputs: List["File"] = relationship("File", secondary=simulation_output_files)
    meta = relationship("MetaData")
    provenance = relationship("Provenance", uselist=False)
    summary = relationship("Summary")
    watchers = relationship("Watcher", secondary=simulation_watchers, lazy='dynamic')

    def __init__(self, manifest: Union[Manifest, None]) -> None:
        """
        Initialise a new Simulation object using the provided Manifest.

        :param manifest: The Manifest to load the data from, or None to create an empty Simulation.
        """
        if manifest is None:
            return
        self.uuid = uuid.uuid1()
        self.datetime = datetime.now()
        self.status = "UNKNOWN"

        for input in manifest.inputs:
            self.inputs.append(File(input.type, input.uri))

        for output in manifest.outputs:
            self.outputs.append(File(output.type, output.uri))

        for key, value in manifest.workflow.items():
            if re.match(r"code[0-9]+", key) and isinstance(value, dict):
                for code_key in value:
                    self.meta.append(MetaData("workflow." + key + "." + code_key, str(value[code_key])))
            else:
                self.meta.append(MetaData("workflow." + key, str(value)))

        self.meta.append(MetaData("description", str(manifest.description)))

        flattened_dict: Dict[str, str] = {}
        _flatten_dict(flattened_dict, manifest.metadata)

        for key, value in flattened_dict.items():
            self.meta.append(MetaData(key, str(value)))

    def __str__(self):
        result = ""
        for name in ("uuid", "alias", "datetime", "status"):
            result += "%s:%s%s\n" % (name, ((10 - len(name)) * " "), getattr(self, name))
        result += "metadata:\n"
        for meta in self.meta:
            if meta.element == "description":
                count = 0
                for line in meta.value.split('\n'):
                    if count == 0:
                        result += "  %s: %s\n" % (meta.element, line)
                    elif line != "":
                        result += "               %s\n" % line
                    count += 1
            else:
                result += "  %s: %s\n" % (meta.element, meta.value)
        result += "inputs:\n"
        for file in self.inputs:
            result += "%s\n" % file
        result += "outputs:\n"
        for file in self.outputs:
            result += "%s\n" % file
        return result

    def find_meta(self, name: str):
        return [m for m in self.meta if m.element == name]

    @classmethod
    def from_data(cls, data: Dict[str, Union[str, Dict, List]]) -> "Simulation":
        simulation = Simulation(None)
        simulation.uuid = uuid.UUID(_checked_get(data, "uuid", str))
        simulation.alias = _checked_get(data, "alias", str)
        simulation.datetime = date_parser.parse(_checked_get(data, "datetime", str))
        simulation.status = _checked_get(data, "status", str)
        if "inputs" in data:
            inputs = _checked_get(data, "inputs", list)
            simulation.inputs = [File.from_data(el) for el in inputs]
        if "outputs" in data:
            outputs = _checked_get(data, "outputs", list)
            simulation.outputs = [File.from_data(el) for el in outputs]
        if "metadata" in data:
            metadata = _checked_get(data, "metadata", list)
            for el in metadata:
                if not isinstance(el, dict):
                    raise Exception("corrupted metadata element - expected dictionary")
                simulation.meta.append(MetaData.from_data(el))
        return simulation

    def data(self, recurse: bool=False) -> Dict[str, Union[str, List]]:
        data = dict(
            uuid=self.uuid.hex,
            alias=self.alias,
            datetime=self.datetime.isoformat(),
            status=self.status
        )
        if recurse:
            data["inputs"] = [f.data(recurse=True) for f in self.inputs]
            data["outputs"] = [f.data(recurse=True) for f in self.outputs]
            data["metadata"] = [m.data(recurse=True) for m in self.meta]
        return data

    def check_files(self):
        for file in chain(self.inputs, self.outputs):
            if file.type == DataObject.Type.UDA:
                from ...uda.checksum import checksum as uda_checksum
                checksum = uda_checksum(file.uri)
            elif file.type == DataObject.Type.IMAS:
                from ...imas.checksum import checksum as imas_checksum
                checksum = imas_checksum(file.uri)
            elif file.type == DataObject.Type.FILE:
                from ...checksum import sha1_checksum
                checksum = sha1_checksum(file.uri.path)
            else:
                raise NotImplementedError("Not implemented for file type " + str(file.type))
            if checksum != file.checksum:
                raise ValueError("Checksum does not not match for file " + str(file))
