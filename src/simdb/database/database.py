import uuid
import os
import sys
import contextlib
from typing import Optional, List, Tuple, Union, TYPE_CHECKING
from enum import Enum, auto
from ..config.config import Config


class DatabaseError(RuntimeError):
    pass


if TYPE_CHECKING or 'sphinx' in sys.modules:
    # Only importing these for type checking and documentation generation in order to speed up runtime startup.
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy import create_engine, func
    from sqlalchemy.orm import sessionmaker
    import sqlalchemy
    from .models import (Base, Simulation, File, MetaData, ValidationParameters, Provenance, ProvenanceMetaData,
                         ControlledVocabulary, Summary)


class SessionMaker:
    _session_maker: "sessionmaker" = None

    @classmethod
    def get(cls) -> "sessionmaker":
        if cls._session_maker is None:
            from sqlalchemy.orm import sessionmaker
            cls._session_maker = sessionmaker()
        return cls._session_maker

    @classmethod
    def create(cls) -> "sqlalchemy.orm.Session":
        return cls.get()()


class Database:
    """
    Class to wrap the database access.
    """
    engine: "sqlalchemy.engine.Engine"
    _session: "sqlalchemy.orm.SessionExtension" = None

    class DBMS(Enum):
        """
        DBMSs supported.
        """
        SQLITE = auto()
        POSTGRESQL = auto()
        MSSQL = auto()

    def __init__(self, db_type: DBMS, **kwargs) -> None:
        from sqlalchemy import create_engine
        from .models import Base

        """
        Create a new Database object.

        :param db_type: The DBMS to use.
        :param kwargs: DBMS specific keyword args:
            SQLITE:
                file: the sqlite database file path
            POSTGRESQL:
                host: the host to connect to
                port: the port to connect to
        """
        new_db = False
        if db_type == Database.DBMS.SQLITE:
            if "file" not in kwargs:
                raise ValueError("Missing file parameter for SQLITE database")
            new_db = (not os.path.exists(kwargs["file"]))
            self.engine: "sqlalchemy.engine.Engine" = create_engine("sqlite:///%(file)s" % kwargs)

        elif db_type == Database.DBMS.POSTGRESQL:
            if "host" not in kwargs:
                raise ValueError("Missing host parameter for POSTGRESQL database")
            if "port" not in kwargs:
                raise ValueError("Missing port parameter for POSTGRESQL database")
            self.engine: "sqlalchemy.engine.Engine" = create_engine("postgresql://%(host)s:%(port)d/simdb" % kwargs)
            with contextlib.closing(self.engine.connect()) as con:
                res: sqlalchemy.engine.ResultProxy = con.execute(
                    "SELECT * FROM pg_catalog.pg_tables WHERE schemaname = 'public';")
                new_db = (res.rowcount == 0)

        elif db_type == Database.DBMS.MSSQL:
            if "user" not in kwargs:
                raise ValueError("Missing user parameter for MSSQL database")
            if "password" not in kwargs:
                raise ValueError("Missing password parameter for MSSQL database")
            if "dsnname" not in kwargs:
                raise ValueError("Missing dsnname parameter for MSSQL database")
            self.engine: "sqlalchemy.engine.Engine" = create_engine("mssql+pyodbc://%(user)s:%(password)s@%(dsnname)s"
                                                                    % kwargs)
            new_db = False

        else:
            raise ValueError("Unknown database type: " + db_type.name)
        if new_db:
            Base.metadata.create_all(self.engine)
        Base.metadata.bind = self.engine
        SessionMaker.get().configure(bind=self.engine)

    def close(self):
        """
        Close the current session
        """
        if self._session:
            self._session.close()

    @property
    def session(self) -> "sqlalchemy.orm.Session":
        if self._session is None:
            self._session: "sqlalchemy.orm.Session" = SessionMaker.create()
        return self._session

    def reset(self) -> None:
        """
        Clear all the data out of the database.

        :return: None
        """
        from .models import Base

        with contextlib.closing(self.engine.connect()) as con:
            trans = con.begin()
            for table in reversed(Base.metadata.sorted_tables):
                con.execute(table.delete())
            trans.commit()

    def list_simulations(self) -> List["Simulation"]:
        """
        Return a list of all the simulations stored in the database.

        :return: A list of Simulations.
        """
        from .models import Simulation

        return self.session.query(Simulation).all()

    def list_files(self) -> List["File"]:
        """
        Return a list of all the files stored in the database.

        :return:  A list of Files.
        """
        from .models import File

        return self.session.query(File).all()

    def list_validation_parameters(self, device: Optional[str], scenario: Optional[str]) -> List["ValidationParameters"]:
        from .models import ValidationParameters

        if device is None and scenario is None:
            return self.session.query(ValidationParameters) \
                .group_by(ValidationParameters.device, ValidationParameters.scenario).all()
        else:
            return self.session.query(ValidationParameters).filter_by(device=device, scenario=scenario).all()

    def list_summaries(self, sim_ref: str) -> List["Summary"]:
        from .models import Simulation

        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = self.session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        return simulation.summary

    def delete_simulation(self, sim_ref: str) -> "Simulation":
        """
        Delete the specified simulation from the database.

        :param sim_ref: The simulation UUID or alias.
        :return: None
        """
        from .models import Simulation

        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = self.session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        for file in simulation.inputs:
            self.session.delete(file)
        self.session.delete(simulation)
        self.session.commit()
        return simulation

    def query_meta(self, equals=None, contains=None) -> List["Simulation"]:
        """
        Query the metadata and return matching simulations.

        :return:
        """
        from .models import Simulation, MetaData
        from sqlalchemy import func

        queries = []

        if equals is None:
            equals = {}
        if contains is None:
            contains = {}

        for name in equals:
            queries.append(self.session.query(Simulation).join(MetaData, Simulation.meta)\
                           .filter(MetaData.element == name,
                                   func.lower(MetaData.value) == equals[name].lower()))

        for name in contains:
            queries.append(self.session.query(Simulation).join(MetaData, Simulation.meta)\
                           .filter(MetaData.element == name,
                                   MetaData.value.ilike("%{}%".format(contains[name]))))

        query = queries[0]
        for i in range(1, len(queries)):
            query = query.intersect(queries[i])

        return query.all()

    def get_simulation(self, sim_ref: str) -> "Simulation":
        """
        Get the specified simulation from the database.

        :param sim_ref: The simulation UUID or alias.
        :return: The Simulation.
        """
        from .models import Simulation

        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            simulation = self.session.query(Simulation).filter_by(alias=sim_ref).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        self.session.commit()
        return simulation

    def get_file(self, file_uuid_str: str) -> "File":
        """
        Get the specified file from the database.

        :param file_uuid_str: The string representation of the file UUID.
        :return: The File.
        """
        from .models import File

        try:
            file_uuid = uuid.UUID(file_uuid_str)
            file = self.session.query(File).filter_by(uuid=file_uuid).one_or_none()
        except ValueError:
            raise DatabaseError("Invalid UUID: " + file_uuid_str)
        if file is None:
            raise DatabaseError("Failed to find file: " + file_uuid.hex)
        self.session.commit()
        return file

    def get_metadata(self, sim_ref: str, name: str) -> List[str]:
        """
        Get all the metadata for the given simulation with the given key.

        :param sim_ref: the simulation identifier
        :param name: the metadata key
        :return: The  matching MetaData.
        """
        from .models import Simulation

        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = self.session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        self.session.commit()
        return [m.value for m in simulation.meta.filter_by(element=name).all()]

    def get_controlled_vocab(self, element) -> List[str]:
        from .models import ControlledVocabulary

        vocab: ControlledVocabulary = self.session.query(ControlledVocabulary).filter_by(name=element).one()
        return [i.value for i in vocab.words]

    def get_provenance(self, sim_ref: str) -> "Provenance":
        """
        Get all the provenance for the given simulation.

        :param sim_ref: the simulation identifier
        :return: The  matching MetaData.
        """
        from .models import Simulation

        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = self.session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        self.session.commit()
        return simulation.provenance

    def query_provenance(self, equals=None, contains=None) -> List["Simulation"]:
        """
        Query the provenance metadata and return matching simulations.

        :return:
        """
        from .models import Simulation, ProvenanceMetaData, Provenance
        from sqlalchemy import func

        queries = []

        if equals is None:
            equals = {}
        if contains is None:
            contains = {}

        for name in equals:
            queries.append(self.session.query(Simulation)\
                           .join(Provenance, Simulation.provenance)\
                           .join(ProvenanceMetaData, Provenance.meta)\
                           .filter(ProvenanceMetaData.element == name,
                                  func.lower(ProvenanceMetaData.value) == equals[name].lower()))

        for name in contains:
            queries.append(self.session.query(Simulation)
                           .join(Provenance, Simulation.provenance)\
                           .join(ProvenanceMetaData, Provenance.meta)\
                           .filter(ProvenanceMetaData.element == name,
                                   ProvenanceMetaData.value.ilike("%{}%".format(contains[name]))))

        query = queries[0]
        for i in range(1, len(queries)):
            query = query.intersect(queries[i])

        return query.all()

    def query_summary(self, equals=None, contains=None) -> List["Simulation"]:
        from .models import Simulation, Summary
        from sqlalchemy import func

        queries = []

        if equals is None:
            equals = {}
        if contains is None:
            contains = {}

        for name in equals:
            queries.append(self.session.query(Simulation).join(Summary, Simulation.summary)\
                           .filter(Summary.key == name,
                                   func.lower(Summary.value) == equals[name].lower()))

        for name in contains:
            queries.append(self.session.query(Simulation).join(Summary, Simulation.summary)\
                           .filter(Summary.key == name,
                                   Summary.value.ilike("%{}%".format(contains[name]))))

        query = queries[0]
        for i in range(1, len(queries)):
            query = query.intersect(queries[i])        

        return query.all()

    def insert_simulation(self, simulation: "Simulation") -> None:
        """
        Insert the given simulation into the database.

        :param simulation: The Simulation to insert.
        :return: None
        """
        from sqlalchemy.exc import DBAPIError

        try:
            self.session.add(simulation)
            self.session.commit()
        except DBAPIError as err:
            self.session.rollback()
            raise DatabaseError(str(err.orig))

    def insert_provenance(self, sim_ref: str, provenance: dict) -> None:
        """
        Insert the given simulation into the database.

        :param simulation: The Simulation to insert.
        :return: None
        """
        from .models import Simulation, Provenance

        simulation: Union[Simulation, None] = None
        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = self.session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        if not simulation.provenance:
            simulation.provenance = Provenance(provenance)
        else:
            simulation.provenance.add_metadata(provenance)
        self.session.commit()

    def insert_summary(self, sim_ref: str, summary: List[Tuple[str, str]]) -> None:
        from .models import Simulation, Summary

        simulation: Union[Simulation, None] = None
        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = self.session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        for (k, v) in summary:
            simulation.summary.append(Summary(k, v))
        self.session.commit()

    def get_validation_parameters(self, device: str, scenario: str, path: str) -> Optional["ValidationParameters"]:
        from .models import ValidationParameters

        return self.session.query(ValidationParameters)\
            .filter_by(device=device, scenario=scenario, path=path)\
            .one_or_none()

    def insert_validation_parameters(self, params: "ValidationParameters") -> None:
        try:
            self.session.add(params)
            self.session.commit()
        except DBAPIError as err:
            self.session.rollback()
            raise DatabaseError(str(err.orig))

    def put_validation_result(self, uuid, path, test_pass, tests, results, stats):
        pass

    def new_vocabulary(self, name: str, words: List[str]) -> None:
        from .models import ControlledVocabulary

        vocab = ControlledVocabulary(name, words)
        self.session.add(vocab)
        self.session.commit()

    def clear_vocabulary_words(self, name: str, words: List[str]) -> None:
        from .models import ControlledVocabulary

        vocab: ControlledVocabulary = self.session.query(ControlledVocabulary).filter_by(name=name).one_or_none()
        if vocab is None:
            raise DatabaseError("Failed to find vocabulary: " + name)
        vocab.add_words(words)
        self.session.commit()

    def clear_vocabulary(self, name: str) -> None:
        from .models import ControlledVocabulary

        vocab: ControlledVocabulary = self.session.query(ControlledVocabulary).filter_by(name=name).one_or_none()
        if vocab is None:
            raise DatabaseError("Failed to find vocabulary: " + name)
        vocab.words.clear()
        self.session.commit()

    def delete_vocabulary(self, name: str) -> None:
        from .models import ControlledVocabulary

        vocab: ControlledVocabulary = self.session.query(ControlledVocabulary).filter_by(name=name).one_or_none()
        if vocab is None:
            raise DatabaseError("Failed to find vocabulary: " + name)
        self.session.delete(vocab)
        self.session.commit()

    def get_vocabularies(self) -> List["ControlledVocabulary"]:
        from .models import ControlledVocabulary

        return self.session.query(ControlledVocabulary).all()

    def get_vocabulary(self, name: str) -> "ControlledVocabulary":
        from .models import ControlledVocabulary

        vocab: ControlledVocabulary = self.session.query(ControlledVocabulary).filter_by(name=name).one_or_none()
        if vocab is None:
            raise DatabaseError("Failed to find vocabulary: " + name)
        return vocab

    def get_aliases(self, prefix: Optional[str]) -> List[str]:
        from .models import Simulation

        if prefix:
            return [el[0] for el in self.session.query(Simulation).filter(Simulation.alias.like(prefix + '%')).values('alias')]
        else:
            return [el[0] for el in self.session.query(Simulation).values('alias')]


def get_local_db(config: Config) -> Database:
    import appdirs
    db_file = config.get_option('db-file', default=os.path.join(appdirs.user_data_dir('simdb'), 'sim.db'))
    db_dir = os.path.dirname(db_file)
    os.makedirs(db_dir, exist_ok=True)
    database = Database(Database.DBMS.SQLITE, file=db_file)
    return database
