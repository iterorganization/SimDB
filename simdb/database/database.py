from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
import sqlalchemy
import uuid
import os
import contextlib
from typing import Optional, List
from enum import Enum, auto

from simdb.cli.manifest import Manifest

from .models import Base, Simulation


class DatabaseError(RuntimeError):
    pass


Session = sessionmaker()


class Database:
    engine: sqlalchemy.engine.Engine

    class Type(Enum):
        SQLITE = auto()
        POSTGRESQL = auto()

    def __init__(self, db_type: Type, **kwargs):
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
        Session.configure(bind=self.engine)

    @classmethod
    def ingest(cls, manifest: Manifest, alias: Optional[str]) -> None:
        simulation = Simulation(manifest)
        simulation.alias = alias
        session: sqlalchemy.orm.Session = Session()
        session.add(simulation)
        session.commit()

    def reset(self) -> None:
        with contextlib.closing(self.engine.connect()) as con:
            trans = con.begin()
            for table in reversed(Base.metadata.sorted_tables):
                con.execute(table.delete())
            trans.commit()

    @classmethod
    def list(cls) -> List[Simulation]:
        session: sqlalchemy.orm.Session = Session()
        return list(session.query(Simulation))

    @classmethod
    def delete(cls, sim_ref: str) -> None:
        session: sqlalchemy.orm.Session = Session()
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
    def get(cls, sim_ref: str) -> Simulation:
        session: sqlalchemy.orm.Session = Session()
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
    def insert(cls, simulation: Simulation) -> None:
        session: sqlalchemy.orm.Session = Session()
        session.add(simulation)
        session.commit()
