from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.exc import DBAPIError
from sqlalchemy import create_engine
import sqlalchemy
import uuid
import os
import contextlib
from typing import Optional, List
from enum import Enum, auto

from simdb.cli.manifest import Manifest

from .models import Base, Simulation, File


class DatabaseError(RuntimeError):
    pass


SessionMaker = sessionmaker()


class Database:
    """
    Class to wrap the database access.
    """
    engine: sqlalchemy.engine.Engine
    _session: sqlalchemy.orm.SessionExtension = None

    class DBMS(Enum):
        """
        DBMSs supported.
        """
        SQLITE = auto()
        POSTGRESQL = auto()

    def __init__(self, db_type: DBMS, **kwargs):
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
                raise DatabaseError("Missing file parameter for SQLITE database")
            new_db = (not os.path.exists(kwargs["file"]))
            self.engine: sqlalchemy.engine.Engine = create_engine("sqlite:///%(file)s" % kwargs)

        elif db_type == Database.DBMS.POSTGRESQL:
            if "host" not in kwargs:
                raise DatabaseError("Missing file host for POSTGRESQL database")
            if "port" not in kwargs:
                raise DatabaseError("Missing file port for POSTGRESQL database")
            self.engine: sqlalchemy.engine.Engine = create_engine("postgresql://%(host)s:%(port)d/simdb" % kwargs)
            with contextlib.closing(self.engine.connect()) as con:
                res: sqlalchemy.engine.ResultProxy = con.execute(
                    "SELECT * FROM pg_catalog.pg_tables WHERE schemaname = 'public';")
                new_db = (res.rowcount == 0)
        else:
            raise DatabaseError("Unknown database type: " + db_type.name)
        if new_db:
            Base.metadata.create_all(self.engine)
        Base.metadata.bind = self.engine
        SessionMaker.configure(bind=self.engine)

    @property
    def session(self) -> sqlalchemy.orm.Session:
        if self._session is None:
            self._session: sqlalchemy.orm.Session = SessionMaker()
        return self._session

    def reset(self) -> None:
        """
        Clear all the data out of the database.

        :return: None
        """
        with contextlib.closing(self.engine.connect()) as con:
            trans = con.begin()
            for table in reversed(Base.metadata.sorted_tables):
                con.execute(table.delete())
            trans.commit()

    def list_simulations(self) -> List[Simulation]:
        """
        Return a list of all the simulations stored in the database.

        :return: A list of Simulations.
        """
        return list(self.session.query(Simulation))

    def list_files(self) -> List[File]:
        """
        Return a list of all the files stored in the database.

        :return:  A list of Files.
        """
        return list(self.session.query(File))

    def delete_simulation(self, sim_ref: str) -> None:
        """
        Delete the specified simulation from the database.

        :param sim_ref: The simulation UUID or alias.
        :return: None
        """
        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = self.session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        self.session.delete(simulation)
        self.session.commit()

    def get_simulation(self, sim_ref: str) -> Simulation:
        """
        Get the specified simulation from the database.

        :param sim_ref: The simulation UUID or alias.
        :return: The Simulation.
        """
        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = self.session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        self.session.commit()
        return simulation

    def get_file(self, file_uuid: str) -> File:
        """
        Get the specified file from the database.

        :param file_uuid: The file UUID.
        :return: The File.
        """
        try:
            file_uuid = uuid.UUID(file_uuid)
            file = self.session.query(File).filter_by(uuid=file_uuid).one_or_none()
        except ValueError:
            raise DatabaseError("Invalid UUID: " + file_uuid)
        if file is None:
            raise DatabaseError("Failed to find file: " + file_uuid.hex)
        self.session.commit()
        return file

    def insert_simulation(self, simulation: Simulation) -> None:
        """
        Insert the given simulation into the database.

        :param simulation: The Simulation to insert.
        :return: None
        """
        try:
            self.session.add(simulation)
            self.session.commit()
        except DBAPIError as err:
            self.session.rollback()
            raise DatabaseError(str(err.orig))
