from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
import sqlalchemy
import uuid
import os
import contextlib
from typing import Optional, List

from simdb.cli.manifest import Manifest

from .models import Base, Simulation


class DatabaseError(RuntimeError):
    pass


Session = sessionmaker()


class Database:
    engine: sqlalchemy.engine.Engine

    def __init__(self):
        db_dir = os.path.join(os.environ["HOME"], ".simdb")
        os.makedirs(db_dir, exist_ok=True)
        db_file = os.path.join(db_dir, "sim.db")
        new_db = (not os.path.exists(db_file))
        self.engine: sqlalchemy.engine.Engine = create_engine("sqlite:///%s" % db_file)
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
