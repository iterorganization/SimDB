import re
import os
import uuid
from typing import Union, List, Dict, Any, Tuple, Type
from datetime import datetime
from dateutil import parser as date_parser
from sqlalchemy import Column, ForeignKey, Table, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import sqlalchemy.types as sql_types

from ..cli.manifest import Manifest, DataObject
from ..docstrings import inherit_docstrings


class UUID(sql_types.TypeDecorator):
    """
    Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as stringified hex values.
    """
    impl = sql_types.CHAR

    def load_dialect_impl(self, dialect):
        from sqlalchemy.dialects import postgresql

        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID())
        else:
            return dialect.type_descriptor(sql_types.CHAR(32))

    def process_literal_param(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value).hex
            else:
                return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class BaseModel:
    """
    Base model for ORM classes.
    """
    def __str__(self):
        """
        Return a string representation of the {cls.__name__} formatted to print.

        :return: The {cls.__name__} as a string for printing.
        """
        raise NotImplementedError

    @classmethod
    def from_data(cls, data: Dict) -> "BaseModel":
        """
        Create a Model from serialised data.

        :param data: Serialised model data.
        :return: The created model.
        """
        raise NotImplementedError

    def data(self, recurse: bool=False) -> Dict:
        """
        Serialise the {cls.__name__}.

        :param recurse: If True also serialise any contained models, otherwise only serialise simple fields.
        :return: The serialised data.
        """
        raise NotImplementedError


Base: Any = declarative_base(cls=BaseModel)


simulation_input_files = Table("simulation_input_files", Base.metadata,
                               Column("simulation_id", sql_types.Integer, ForeignKey("simulations.id")),
                               Column("file_id", sql_types.Integer, ForeignKey("files.id")))


simulation_output_files = Table("simulation_output_files", Base.metadata,
                                Column("simulation_id", sql_types.Integer, ForeignKey("simulations.id")),
                                Column("file_id", sql_types.Integer, ForeignKey("files.id")))


def _get_imas_paths(imas: Dict) -> List[str]:
    if "IMAS_VERSION" not in os.environ:
        raise Exception("$IMAS_VERSION not defined")
    imas_version = os.environ["IMAS_VERSION"]
    imas_file_base = "ids_%d%04d" % (imas["shot"], imas["run"])
    if "path" in imas:
        path = os.path.join(imas["path"], imas_version.split(".")[0], "0")
    else:
        if "MDSPLUS_TREE_BASE_0" not in os.environ:
            raise Exception("path not specified for IDS and $MDSPLUS_TREE_BASE_0 not defined")
        path = os.environ["MDSPLUS_TREE_BASE_0"]
    return [
        os.path.join(path, imas_file_base + ".characteristics"),
        os.path.join(path, imas_file_base + ".datafile"),
        os.path.join(path, imas_file_base + ".tree"),
    ]


def _checked_get(data: Dict[str, Any], key, type: Type):
    if not isinstance(data[key], type):
        raise ValueError("corrupted %s - expected %s" % (key, type.name))
    return data[key]


@inherit_docstrings
class Simulation(Base):
    """
    Class to represent simulations in the database ORM.
    """
    __tablename__ = "simulations"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False, unique=True)
    # metadata_id = Column(Integer, ForeignKey(MetaData.id))
    alias = Column(sql_types.String(250), nullable=True, unique=True)
    datetime = Column(sql_types.DateTime, nullable=False)
    status = Column(sql_types.String(20), nullable=False)
    inputs: List["File"] = relationship("File", secondary=simulation_input_files)
    outputs: List["File"] = relationship("File", secondary=simulation_output_files)
    meta = relationship("MetaData")
    provenance = relationship("Provenance", uselist=False)
    summary = relationship("Summary")

    @staticmethod
    def _append_file(file_list: List, data_obj: DataObject):
        if data_obj.type == DataObject.Type.PATH:
            file_list.append(File(data_obj.type, os.path.dirname(data_obj.path), os.path.basename(data_obj.path)))
        elif data_obj.type == DataObject.Type.IMAS:
            for path in _get_imas_paths(data_obj.imas):
                file_list.append(File(data_obj.type, os.path.dirname(path), os.path.basename(path)))
        elif data_obj.type == DataObject.Type.UDA:
            file_list.append(File(data_obj.type, data_obj.uda["source"], data_obj.uda["signal"]))
        elif data_obj.type == DataObject.Type.UUID:
            return
        else:
            raise NotImplementedError("source type " + data_obj.type.name + " not yet implemented")

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
            self._append_file(self.inputs, input)

        for output in manifest.outputs:
            self._append_file(self.outputs, output)

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


@inherit_docstrings
class File(Base):
    """
    Class to represent files in the database ORM.
    """
    __tablename__ = "files"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False, unique=True)
    usage = Column(sql_types.String(250), nullable=True)
    file_name = Column(sql_types.String(250), nullable=False)
    directory = Column(sql_types.String(250), nullable=True)
    checksum = Column(sql_types.String(40), nullable=True)
    type: DataObject.Type = Column(sql_types.Enum(DataObject.Type), nullable=True)
    purpose = Column(sql_types.String(250), nullable=True)
    sensitivity = Column(sql_types.String(20), nullable=True)
    access = Column(sql_types.String(20), nullable=True)
    embargo = Column(sql_types.String(20), nullable=True)
    datetime = Column(sql_types.DateTime, nullable=False)

    def _integrity_check(self) -> None:
        if self.type == DataObject.Type.UDA:
            from ..uda.checksum import checksum as uda_checksum
            self.checksum = uda_checksum(self.file_name, self.directory)
        else:
            from ..checksum import sha1_checksum
            if os.path.isfile(os.path.join(self.directory, self.file_name)):
                self.checksum = sha1_checksum(os.path.join(self.directory, self.file_name))
            else:
                print('**** File does not exist ****')

    def __init__(self, type: DataObject.Type, directory: str, file_name: str, perform_integrity_check: bool=True) -> None:
        """
        Initialise the File object using the provided DataObject.

        :param data_object: The DataObject to load the data from, or None to create an empty File.
        """
        self.uuid = uuid.uuid1()
        self.file_name = file_name
        self.directory = directory
        self.type = type
        self.datetime = datetime.now()

        if perform_integrity_check:
            self._integrity_check()

    def __str__(self):
        result = ""
        for name in ("uuid", "usage", "file_name", "directory", "checksum", "type", "purpose", "sensitivity", "access",
                     "embargo", "datetime"):
            result += "  %s:%s%s\n" % (name, ((14 - len(name)) * " "), getattr(self, name))
        return result

    def __repr__(self):
        result = "%s (%s)" % (self.uuid, self.file_name)
        return result

    @classmethod
    def from_data(cls, data: Dict) -> "File":
        file = File(DataObject.Type[data["type"]], data["directory"], data["file_name"], perform_integrity_check=False)
        file.uuid = uuid.UUID(data["uuid"])
        file.usage = data["usage"]
        file.checksum = data["checksum"]
        file.purpose = data["purpose"]
        file.sensitivity = data["sensitivity"]
        file.access = data["access"]
        file.embargo = data["embargo"]
        file.datetime = date_parser.parse(data["datetime"])
        return file

    def data(self, recurse: bool=False) -> Dict[str, str]:
        data = dict(
            uuid=self.uuid.hex,
            usage=self.usage,
            file_name=self.file_name,
            directory=self.directory,
            checksum=self.checksum,
            type=self.type.name,
            purpose=self.purpose,
            sensitivity=self.sensitivity,
            access=self.access,
            embargo=self.embargo,
            datetime=self.datetime.isoformat(),
        )
        return data


@inherit_docstrings
class MetaData(Base):
    """
    Class to represent metadata in the database ORM.
    """
    __tablename__ = "metadata"
    id = Column(sql_types.Integer, primary_key=True)
    sim_id = Column(sql_types.Integer, ForeignKey(Simulation.id))
    uuid = Column(UUID, nullable=False)
    element = Column(sql_types.String(250), nullable=False)
    value = Column(sql_types.Text, nullable=True)

    def __init__(self, key: str, value: str) -> None:
        self.uuid = uuid.uuid1()
        self.element = key
        self.value = value

    def __str__(self):
        return "{}: {}".format(self.element, self.value)

    @classmethod
    def from_data(cls, data: Dict) -> "MetaData":
        meta = MetaData(data["element"], data["value"])
        meta.uuid = uuid.UUID(data["uuid"])
        return meta

    def data(self, recurse: bool=False) -> Dict[str, str]:
        data = dict(
            uuid=self.uuid.hex,
            element=self.element,
            value=self.value,
        )
        return data


# @inherit_docstrings
# class ValidationParameter(Base):
#     """
#     Class to represent validation parameters in the database ORM.
#     """
#     __tablename__ = "validation_parameters"
#     id = Column(sql_types.Integer, primary_key=True)
#     element = Column(Text, nullable=False)
#     name = Column(sql_types.String(50), nullable=False)
#     value = Column(Float, nullable=False)
#
#     def __init__(self, element: str, name: str, value: float):
#         self.element = element
#         self.name = name
#         self.value = value
#
#     @classmethod
#     def from_data(cls, data: Dict) -> "ValidationParameter":
#         param = ValidationParameter(data["element"], data["name"], data["value"])
#         return param
#
#     def data(self, recurse: bool=False) -> Dict:
#         data = dict(
#             element=self.element,
#             name=self.name,
#             value=self.value
#         )
#         return data


def _flatten_dict(out_dict: Dict[str, str], in_dict: Dict[str, Union[Dict, List, Any]], prefix: Tuple=()):
    for key, value in in_dict.items():
        if isinstance(value, dict):
            _flatten_dict(out_dict, value, prefix + (key,))
        elif isinstance(value, list):
            for el in value:
                _flatten_dict(out_dict, {key: el}, prefix)
        else:
            out_dict['.'.join(prefix + (key,))] = str(value)


@inherit_docstrings
class Provenance(Base):
    """
    Class to represent provenance in the database ORM.
    """
    __tablename__ = "provenance"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    sim_id = Column(sql_types.Integer, ForeignKey(Simulation.id))
    meta = relationship("ProvenanceMetaData")
    signals = relationship("ProvenanceSignal")

    def __init__(self, metadata: Dict) -> None:
        self.uuid = uuid.uuid1()
        self.add_metadata(metadata)
        self.add_signals()

    def add_metadata(self, metadata: Dict):
        flattened_dict: Dict[str, str] = {}
        _flatten_dict(flattened_dict, metadata)

        for key, value in flattened_dict.items():
            self.meta.append(ProvenanceMetaData(key, value))

    def add_signals(self):
        pass

    @classmethod
    def from_data(cls, data: Dict) -> "Provenance":
        prov = Provenance(data["meta"])
        prov.uuid = data["uuid"]
        return prov

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            element=self.element,
            value=self.value,
        )
        if recurse:
            data["meta"] = [m.data(recurse=True) for m in self.meta]
        return data

    def __str__(self):
        s = "MetaData:\n"
        for meta in self.meta:
            s += ("  " + str(meta))
        s += "Signals:\n"
        for signal in self.signals:
            s += ("  " + str(signal))
        return s


@inherit_docstrings
class ProvenanceMetaData(Base):
    """
    Class to represent provenance metadata in the database ORM.
    """
    __tablename__ = "provenance_metadata"
    id = Column(sql_types.Integer, primary_key=True)
    prov_id = Column(sql_types.Integer, ForeignKey(Provenance.id))
    uuid = Column(UUID, nullable=False)
    element = Column(sql_types.String(250), nullable=False)
    value = Column(sql_types.Text, nullable=True)

    def __init__(self, key: str, value: str) -> None:
        self.uuid = uuid.uuid1()
        self.element = key
        self.value = value

    @classmethod
    def from_data(cls, data: Dict) -> "ProvenanceMetaData":
        meta = ProvenanceMetaData(data["element"], data["value"])
        meta.uuid = data["uuid"]
        return meta

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            element=self.element,
            value=self.value,
        )
        return data

    def __str__(self):
        s = "{}: {}\n".format(self.element, self.value)
        return s


@inherit_docstrings
class ProvenanceSignal(Base):
    """
    Class to represent provenance signal request in the database ORM.
    """
    __tablename__ = "provenance_signal"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    prov_id = Column(sql_types.Integer, ForeignKey(Provenance.id))
    requested_signal = Column(sql_types.Text, nullable=False)
    requested_source = Column(sql_types.Text, nullable=False)
    mapped_signal = Column(sql_types.Text, nullable=False)
    mapped_source = Column(sql_types.Text, nullable=False)
    mapped_source_uuid = Column(UUID, nullable=False)

    def __init__(self, requested_signal: str, requested_source: str, mapped_signal: str, mapped_source: str,
                 mapped_source_uuid: str) -> None:
        self.uuid = uuid.uuid1()
        self.requested_signal = requested_signal
        self.requested_source = requested_source
        self.mapped_signal = mapped_signal
        self.mapped_source = mapped_source
        self.mapped_source_uuid = uuid.UUID(mapped_source_uuid)

    @classmethod
    def from_data(cls, data: Dict) -> "ProvenanceMetaData":
        prov_signal = ProvenanceSignal(data["requested_signal"], data["requested_source"], data["mapped_signal"],
                                       data["mapped_source"], data["mapped_source_uuid"])
        prov_signal.uuid = data["uuid"]
        return prov_signal

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            requested_signal=self.requested_signal,
            requested_source=self.requested_source,
            mapped_signal=self.mapped_signal,
            mapped_source=self.mapped_source,
            mapped_source_uuid=self.mapped_source_uuid.hex,
        )
        return data


@inherit_docstrings
class ControlledVocabulary(Base):
    """
    Class to represent controlled vocabularies in the database ORM.
    """
    __tablename__ = "controlled_vocabulary"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    name = Column(sql_types.String(250), nullable=False, unique=True)
    words: List["ControlledVocabularyWord"] = relationship("ControlledVocabularyWord")

    def __init__(self, name: str, words: List[str]) -> None:
        self.uuid = uuid.uuid1()
        self.name = name
        self.add_words(words)

    def add_words(self, words: List[str]):
        for word in words:
            self.words.append(ControlledVocabularyWord(word))

    @classmethod
    def from_data(cls, data: Dict) -> "ControlledVocabulary":
        vocab = ControlledVocabulary(data["name"], data["words"])
        vocab.uuid = data["uuid"]
        return vocab

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            name=self.name,
        )
        if recurse:
            data["words"] = [w.data(recurse=True) for w in self.words]
        return data


@inherit_docstrings
class ControlledVocabularyWord(Base):
    """
    Class to represent controlled vocabulary word in the database ORM.
    """
    __tablename__ = "controlled_vocabulary_word"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    vocabulary_id = Column(sql_types.Integer, ForeignKey(ControlledVocabulary.id))
    value = Column(sql_types.Text, nullable=False)
    __table_args__ = (
        UniqueConstraint('vocabulary_id', 'value', name='_vocabulary_word'),
    )

    def __init__(self, value: str) -> None:
        self.uuid = uuid.uuid1()
        self.value = value

    @classmethod
    def from_data(cls, data: Dict) -> "ControlledVocabularyWord":
        word = ControlledVocabularyWord(data["value"])
        word.uuid = data["uuid"]
        return word

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            value=self.value,
        )
        return data


@inherit_docstrings
class ValidationParameters(Base):
    __tablename__ = "validation_parameters"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    device = Column(sql_types.Text, nullable=False)
    scenario = Column(sql_types.Text, nullable=False)
    path = Column(sql_types.Text, nullable=False)
    mandatory = Column(sql_types.Boolean, nullable=False)
    range_low = Column(sql_types.Float, nullable=False)
    range_high = Column(sql_types.Float, nullable=False)
    mean_low = Column(sql_types.Float, nullable=False)
    mean_high = Column(sql_types.Float, nullable=False)
    median_low = Column(sql_types.Float, nullable=False)
    median_high = Column(sql_types.Float, nullable=False)
    stdev_low = Column(sql_types.Float, nullable=False)
    stdev_high = Column(sql_types.Float, nullable=False)
    mandatory_tests = Column(sql_types.Text, nullable=False)

    __table_args__ = (
        UniqueConstraint('device', 'scenario', 'path', name='_validation_parameters_identifier'),
    )

    def __init__(self, device: str, scenario: str, path: str, mandatory: bool, range_low: float, range_high: float,
                 mean_low: float, mean_high: float, median_low: float, median_high: float,
                 stdev_low: float, stdev_high: float, mandatory_tests: str) -> None:
        self.uuid = uuid.uuid1()
        self.device = device
        self.scenario = scenario
        self.path = path
        self.mandatory = mandatory
        self.range_low = range_low
        self.range_high = range_high
        self.mean_low = mean_low
        self.mean_high = mean_high
        self.median_low = median_low
        self.median_high = median_high
        self.stdev_low = stdev_low
        self.stdev_high = stdev_high
        self.mandatory_tests = mandatory_tests

    @classmethod
    def from_data(cls, data: Dict) -> "ValidationParameters":
        params = ValidationParameters(data["device"], data["scenario"], data["path"], data["mandatory"],
                                      data["range_low"], data["range_high"], data["mean_low"], data["mean_high"],
                                      data["median_low"], data["median_high"], data["stdev_low"], data["stdev_high"],
                                      data["mandatory_tests"])
        params.uuid = data["uuid"]
        return params

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            device=self.device,
            scenario=self.scenario,
            path=self.path,
            mandatory=self.mandatory,
            range_low=self.range_low,
            range_high=self.range_high,
            mean_low=self.mean_low,
            mean_high=self.mean_high,
            median_low=self.median_low,
            median_high=self.median_high,
            stdev_low=self.stdev_low,
            stdev_high=self.stdev_high,
            mandatory_tests=self.mandatory_tests,
        )
        return data


@inherit_docstrings
class Summary(Base):
    """
    Class to represent metadata in the database ORM.
    """
    __tablename__ = "summary"
    id = Column(sql_types.Integer, primary_key=True)
    sim_id = Column(sql_types.Integer, ForeignKey(Simulation.id))
    uuid = Column(UUID, nullable=False)
    key = Column(sql_types.String(250), nullable=False)
    value = Column(sql_types.Text, nullable=True)

    __table_args__ = (
        UniqueConstraint('sim_id', 'key', name='_simulation_summary'),
    )

    def __init__(self, key: str, value: str) -> None:
        self.uuid = uuid.uuid1()
        self.key = key
        self.value = value

    @classmethod
    def from_data(cls, data: Dict) -> "Summary":
        summary = Summary(data["key"], data["value"])
        summary.uuid = data["uuid"]
        return summary

    def data(self, recurse: bool=False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            key=self.key,
            value=self.value,
        )
        return data
