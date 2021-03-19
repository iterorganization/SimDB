import uuid
import os
import sys
import contextlib
from typing import Optional, List, Tuple, Union, TYPE_CHECKING, cast, Any
from enum import Enum, auto
from ..config import Config


class DatabaseError(RuntimeError):
    pass


if TYPE_CHECKING or 'sphinx' in sys.modules:
    # Only importing these for type checking and documentation generation in order to speed up runtime startup.
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy import create_engine, func
    from sqlalchemy.orm import scoped_session, sessionmaker
    import sqlalchemy
    from .models import (Base, Simulation, File, MetaData, ValidationParameters, Provenance, ProvenanceMetaData,
                         ControlledVocabulary, Summary, Watcher)

    class Session(scoped_session):
        def query(self, obj: Base) -> Any:
            pass

        def commit(self):
            pass

        def delete(self, obj: Base):
            pass

        def add(self, obj: Base):
            pass

        def rollback(self):
            pass


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

    def __init__(self, db_type: DBMS, scopefunc=None, **kwargs) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker, scoped_session
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
        if scopefunc is None:
            scopefunc = lambda: 0
        self.session: "Session" = cast("Session", scoped_session(sessionmaker(bind=self.engine), scopefunc=scopefunc))

    @classmethod
    def _is_short_uuid(cls, sim_id: str):
        return len(sim_id) == 8 and sim_id.isalnum()

    def _find_simulation(self, sim_ref: str) -> "Simulation":
        from .models import Simulation
        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            simulation = None
            if self._is_short_uuid(sim_ref):
                simulation = self.session.query(Simulation).filter(Simulation.uuid.startswith(sim_ref)).one_or_none()
            if not simulation:
                sim_alias = sim_ref
                simulation = self.session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
            if not simulation:
                raise DatabaseError(f"Simulation {sim_ref} not found.")
        return simulation

    def remove(self):
        """
        Remove the current session
        """
        if self.session:
            self.session.remove()

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

    def delete_simulation(self, sim_ref: str) -> "Simulation":
        """
        Delete the specified simulation from the database.

        :param sim_ref: The simulation UUID or alias.
        :return: None
        """
        simulation = self._find_simulation(sim_ref)
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
        from sqlalchemy import func, String
        from sqlalchemy.sql.expression import cast

        queries = []

        if equals is None:
            equals = {}
        if contains is None:
            contains = {}

        for name in equals:
            if name == 'alias':
                queries.append(self.session.query(Simulation)
                               .filter(func.lower(Simulation.alias) == equals[name].lower()))
            elif name == 'uuid':
                queries.append(self.session.query(Simulation).filter(Simulation.uuid == uuid.UUID(equals[name])))
            else:
                queries.append(self.session.query(Simulation).join(MetaData, Simulation.meta)
                               .filter(MetaData.element == name,
                                       func.lower(MetaData.value) == equals[name].lower()))

        for name in contains:
            if name == 'alias':
                queries.append(self.session.query(Simulation)
                               .filter(Simulation.alias.ilike("%{}%".format(contains[name]))))
            elif name == 'uuid':
                queries.append(self.session.query(Simulation)
                               .filter(func.REPLACE(cast(Simulation.uuid, String), '-', '')
                                       .ilike("%{}%".format(contains[name].replace('-', '')))))
            else:
                queries.append(self.session.query(Simulation).join(MetaData, Simulation.meta)
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
        simulation = self._find_simulation(sim_ref)
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
            raise DatabaseError(f"Invalid UUID {file_uuid_str}.")
        if file is None:
            raise DatabaseError(f"Failed to find file {file_uuid.hex}.")
        self.session.commit()
        return file

    def get_metadata(self, sim_ref: str, name: str) -> List[str]:
        """
        Get all the metadata for the given simulation with the given key.

        :param sim_ref: the simulation identifier
        :param name: the metadata key
        :return: The  matching MetaData.
        """
        simulation = self._find_simulation(sim_ref)
        self.session.commit()
        return [m.value for m in simulation.meta.filter_by(element=name).all()]

    def add_watcher(self, sim_ref: str, watcher: "Watcher"):
        sim = self._find_simulation(sim_ref)
        sim.watchers.append(watcher)
        self.session.commit()

    def remove_watcher(self, sim_ref: str, username: str):
        sim = self._find_simulation(sim_ref)
        watchers = sim.watchers.filter_by(username=username).all()
        if not watchers:
            raise DatabaseError(f"Watcher not found for simulation {sim_ref}.")
        for watcher in watchers:
            sim.watchers.remove(watcher)
        self.session.commit()

    def list_watchers(self, sim_ref: str) -> List["Watcher"]:
        return self._find_simulation(sim_ref).watchers.all()

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

    def get_aliases(self, prefix: Optional[str]) -> List[str]:
        from .models import Simulation

        if prefix:
            return [el[0] for el in
                    self.session.query(Simulation).filter(Simulation.alias.like(prefix + '%')).values('alias')]
        else:
            return [el[0] for el in self.session.query(Simulation).values('alias')]


def get_local_db(config: Config) -> Database:
    import appdirs
    db_file = config.get_option('db.file', default=os.path.join(appdirs.user_data_dir('simdb'), 'sim.db'))
    db_dir = os.path.dirname(db_file)
    os.makedirs(db_dir, exist_ok=True)
    database = Database(Database.DBMS.SQLITE, file=db_file)
    return database
