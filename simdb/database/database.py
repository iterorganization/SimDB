from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
import sqlalchemy
import uuid
import os
import contextlib
from typing import Optional, List, Type
from enum import Enum, auto

from simdb.cli.manifest import Manifest

from .models import Base, Simulation, File


class DatabaseError(RuntimeError):
    pass


SessionMaker = sessionmaker()


def new_session() -> sqlalchemy.orm.Session:
    return SessionMaker()


class Database:
    """
    Class to wrap the database access.
    """
    engine: sqlalchemy.engine.Engine

    class Type(Enum):
        """
        DBMSs supported.
        """
        SQLITE = auto()
        POSTGRESQL = auto()

    def __init__(self, db_type: Type, **kwargs):
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
        if db_type == Database.Type.SQLITE:
            if "file" not in kwargs:
                raise DatabaseError("Missing file parameter for SQLITE database")
            new_db = (not os.path.exists(kwargs["file"]))
            self.engine: sqlalchemy.engine.Engine = create_engine("sqlite:///%(file)s" % kwargs)

        elif db_type == Database.Type.POSTGRESQL:
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

    @classmethod
    def ingest(cls, manifest: Manifest, alias: Optional[str]) -> None:
        """
        Ingest the given manifest into the database.

        :param manifest: The manifest to ingest.
        :param alias: An optional alias to given to the manifest.
        :return: None
        """
        simulation = Simulation(manifest)
        simulation.alias = alias
        session = new_session()
        session.add(simulation)
        session.commit()

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

    @classmethod
    def list_simulations(cls) -> List[Simulation]:
        """
        Return a list of all the simulations stored in the database.

        :return: A list of Simulations.
        """
        session = new_session()
        return list(session.query(Simulation))

    @classmethod
    def list_files(cls) -> List[File]:
        """
        Return a list of all the files stored in the database.

        :return:  A list of Files.
        """
        session = new_session()
        return list(session.query(File))

    @classmethod
    def delete_simulation(cls, sim_ref: str) -> None:
        """
        Delete the specified simulation from the database.

        :param sim_ref: The simulation UUID or alias.
        :return: None
        """
        session = new_session()
        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        session.delete(simulation)
        session.commit()

    @classmethod
    def get_simulation(cls, sim_ref: str) -> Simulation:
        """
        Get the specified simulation from the database.

        :param sim_ref: The simulation UUID or alias.
        :return: The Simulation.
        """
        session = new_session()
        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
        except ValueError:
            sim_alias = sim_ref
            simulation = session.query(Simulation).filter_by(alias=sim_alias).one_or_none()
        if simulation is None:
            raise DatabaseError("Failed to find simulation: " + sim_ref)
        return simulation

    @classmethod
    def get_file(cls, file_uuid: str) -> File:
        """
        Get the specified file from the database.

        :param file_uuid: The file UUID.
        :return: The File.
        """
        session = new_session()
        try:
            file_uuid = uuid.UUID(file_uuid)
            file = session.query(File).filter_by(uuid=file_uuid).one_or_none()
        except ValueError:
            raise DatabaseError("Invalid UUID: " + file_uuid)
        if file is None:
            raise DatabaseError("Failed to find file: " + file_uuid.hex)
        return file

    @classmethod
    def insert_simulation(cls, simulation: Simulation) -> None:
        """
        Insert the given simulation into the database.

        :param simulation: The Simulation to insert.
        :return: None
        """
        session = new_session()
        session.add(simulation)
        session.commit()
