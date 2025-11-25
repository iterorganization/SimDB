from datetime import datetime
import uuid
import os
import sys
import contextlib
from typing import Optional, List, Tuple, TYPE_CHECKING, cast, Any, Iterable
from enum import Enum, auto

from ..config import Config


class DatabaseError(RuntimeError):
    pass


TYPING = TYPE_CHECKING or "sphinx" in sys.modules

if TYPING:
    # Only importing these for type checking and documentation generation in order to speed up runtime startup.
    from sqlalchemy.orm import scoped_session
    import sqlalchemy
    from .models import Base
    from .models.simulation import Simulation
    from .models.file import File
    from .models.watcher import Watcher
    from ..query import QueryType

    class Session(scoped_session):
        def query(self, obj: Base, *args, **kwargs) -> Any:
            pass

        def commit(self):
            pass

        def delete(self, obj: Base):
            pass

        def add(self, obj: Base, *args, **kwargs):
            pass

        def rollback(self):
            pass


def _is_hex_string(string: str) -> bool:
    try:
        int(string, 16)
        return True
    except ValueError:
        return False


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
                host:       the host to connect to
                port:       the port to connect to
                user:       the user to connect as [optional, defaults to simdb]
                password:   the password for the user [optional, defaults to simdb]
                db_name:    the database name [optional, defaults to simdb]
        """
        if db_type == Database.DBMS.SQLITE:
            if "file" not in kwargs:
                raise ValueError("Missing file parameter for SQLITE database")
            # new_db = (not os.path.exists(kwargs["file"]))
            self.engine: "sqlalchemy.engine.Engine" = create_engine(
                "sqlite:///%(file)s" % kwargs
            )
            with contextlib.closing(self.engine.connect()) as con:
                res: sqlalchemy.engine.ResultProxy = con.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
                )
                new_db = res.rowcount == -1

        elif db_type == Database.DBMS.POSTGRESQL:
            if "host" not in kwargs:
                raise ValueError("Missing host parameter for POSTGRESQL database")
            if "port" not in kwargs:
                raise ValueError("Missing port parameter for POSTGRESQL database")
            kwargs.setdefault("user", "simdb")
            kwargs.setdefault("password", "simdb")
            kwargs.setdefault("db_name", "simdb")
            # self.engine: "sqlalchemy.engine.Engine" = create_engine(
            #     "postgresql://%(user)s:%(password)s@%(host)s:%(port)d/%(db_name)s"
            #     % kwargs
            # )
            self.engine: "sqlalchemy.engine.Engine" = create_engine(
                "postgresql+psycopg2://%(user)s:%(password)s@%(host)s:%(port)s/%(db_name)s"
                % kwargs,
                pool_size=25,
                max_overflow=50,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            with contextlib.closing(self.engine.connect()) as con:
                res: sqlalchemy.engine.ResultProxy = con.execute(
                    "SELECT * FROM pg_catalog.pg_tables WHERE schemaname = 'public';"
                )
                new_db = res.rowcount == 0

        elif db_type == Database.DBMS.MSSQL:
            if "user" not in kwargs:
                raise ValueError("Missing user parameter for MSSQL database")
            if "password" not in kwargs:
                raise ValueError("Missing password parameter for MSSQL database")
            if "dsnname" not in kwargs:
                raise ValueError("Missing dsnname parameter for MSSQL database")
            self.engine: "sqlalchemy.engine.Engine" = create_engine(
                "mssql+pyodbc://%(user)s:%(password)s@%(dsnname)s" % kwargs
            )
            new_db = False

        else:
            raise ValueError("Unknown database type: " + db_type.name)
        if new_db:
            Base.metadata.create_all(self.engine)
        Base.metadata.bind = self.engine
        if scopefunc is None:

            def scopefunc():
                return 0

        self.session: "Session" = cast(
            "Session",
            scoped_session(sessionmaker(bind=self.engine), scopefunc=scopefunc),
        )

    def close(self):
        """Close the database session and dispose of the engine."""
        if hasattr(self, 'session'):
            self.session.remove()  # For scoped_session
        if hasattr(self, 'engine'):
            self.engine.dispose()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def _get_simulation_data(self, limit, query, meta_keys, page) -> Tuple[int, List]:
        if limit:
            limit = limit * len(meta_keys) if meta_keys else limit
            limit_query = query.limit(limit).offset((page - 1) * limit)
        else:
            limit_query = self.get_simulation_data(query)
        data = {}
        for row in limit_query:
            data.setdefault(
                row.simulation.uuid,
                {
                    "alias": row.simulation.alias,
                    "uuid": row.simulation.uuid,
                    "datetime": row.simulation.datetime.isoformat(),
                    "metadata": [],
                },
            )
            if meta_keys:
                data[row.simulation.uuid]["metadata"].append(
                    {"element": row.metadata.element, "value": row.metadata.value}
                )
        if meta_keys:
            return query.count() / len(meta_keys), list(data.values())
        else:
            return query.count(), list(data.values())

    def _find_simulation(self, sim_ref: str) -> "Simulation":
        from .models.simulation import Simulation
        from sqlalchemy import cast as sql_cast, Text, or_ as sql_or
        from sqlalchemy.orm import joinedload
        from sqlalchemy.exc import SQLAlchemyError

        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = (
                self.session.query(Simulation)
                .options(joinedload(Simulation.meta))
                .filter_by(uuid=sim_uuid)
                .one_or_none()
            )
        except ValueError:
            try:
                simulation = (
                    self.session.query(Simulation)
                    .options(joinedload(Simulation.meta))
                    .filter(
                        sql_or(
                            sql_cast(Simulation.uuid, Text).startswith(sim_ref),
                            Simulation.alias == sim_ref,
                        )
                    )
                    .one_or_none()
                )
            except SQLAlchemyError:
                simulation = None
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

    def list_simulations(
        self, meta_keys: List[str] = None, limit: int = 0
    ) -> List["Simulation"]:
        """
        Return a list of all the simulations stored in the database.

        :return: A list of Simulations.
        """
        from .models.simulation import Simulation
        from .models.metadata import MetaData
        from sqlalchemy.orm import joinedload

        if meta_keys:
            query = (
                self.session.query(Simulation)
                .options(joinedload(Simulation.meta))
                .outerjoin(Simulation.meta)
                .filter(MetaData.element.in_(meta_keys))
            )
            if limit:
                query = query.limit(limit)
            return query.all()
        else:
            query = self.session.query(Simulation)
            if limit:
                query = query.limit(limit)
            return query.all()

    def list_simulation_data(
        self,
        meta_keys: List[str] = None,
        limit: int = 0,
        page: int = 1,
        sort_by: str = "",
        sort_asc: bool = False,
    ) -> Tuple[int, List[dict]]:
        """
        Return a list of all the simulations stored in the database.

        :return: A list of Simulations.
        """
        from .models.simulation import Simulation
        from .models.metadata import MetaData
        from sqlalchemy.orm import Bundle
        from sqlalchemy import or_, func, desc, asc

        sort_query = None
        if sort_by:
            sort_dir = asc if sort_asc else desc
            sort_query = (
                self.session.query(
                    Simulation.id,
                    func.row_number()
                    .over(order_by=sort_dir(MetaData.value))
                    .label("row_num"),
                )
                .join(Simulation.meta)
                .filter(MetaData.element == sort_by)
                .subquery()
            )

        if meta_keys:
            s_b = Bundle(
                "simulation", Simulation.alias, Simulation.uuid, Simulation.datetime
            )
            m_b = Bundle("metadata", MetaData.element, MetaData.value)
            query = self.session.query(s_b, m_b).outerjoin(Simulation.meta)

            names_filters = []
            for name in meta_keys:
                if name in ("alias", "uuid"):
                    continue
                names_filters.append(m_b.c.element.ilike(name))
            if names_filters:
                query = query.filter(or_(*names_filters))

            if sort_query is not None:
                query = query.join(
                    sort_query, Simulation.id == sort_query.c.id
                ).order_by(sort_query.c.row_num)

            return self._get_simulation_data(limit, query, meta_keys, page)
        else:
            query = self.session.query(
                Simulation.alias, Simulation.uuid, Simulation.datetime
            )

            if sort_query is not None:
                query = query.join(
                    sort_query, Simulation.id == sort_query.c.id
                ).order_by(sort_query.c.row_num)

            limit_query = (
                query.limit(limit).offset((page - 1) * limit) if limit else query
            )
            return query.count(), [
                {"alias": alias, "uuid": uuid, "datetime": datetime.isoformat()}
                for alias, uuid, datetime in limit_query
            ]

    def get_simulation_data(self, query):
        limit_query = query
        return limit_query

    def list_files(self) -> List["File"]:
        """
        Return a list of all the files stored in the database.

        :return:  A list of Files.
        """
        from .models.file import File

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
        for file in simulation.outputs:
            self.session.delete(file)
        self.session.delete(simulation)
        self.session.commit()
        return simulation

    def _get_metadata(
        self, constraints: List[Tuple[str, str, "QueryType"]]
    ) -> Iterable:
        from sqlalchemy import func, String, or_
        from sqlalchemy.orm import Bundle
        from ..query import QueryType
        from .models.simulation import Simulation
        from .models.metadata import MetaData

        m_b = Bundle("metadata", MetaData.element, MetaData.value)
        s_b = Bundle("simulation", Simulation.id, Simulation.alias, Simulation.uuid)
        query = self.session.query(m_b, s_b).join(Simulation)
        for name, value, query_type in constraints:
            date_time = datetime.now()
            if name == "creation_date":
                date_time = datetime.strptime(value.replace("_", ":"), "%Y-%m-%d %H:%M:%S")
            if query == QueryType.NONE:
                pass
            elif query_type == QueryType.EQ:
                if name == "alias":
                    query = query.filter(func.lower(Simulation.alias) == value.lower())
                elif name == "uuid":
                    query = query.filter(Simulation.uuid == uuid.UUID(value))
                elif name == "creation_date":
                    query = query.filter(Simulation.datetime == date_time)
            elif query_type == QueryType.IN:
                if name == "alias":
                    query = query.filter(Simulation.alias.ilike("%{}%".format(value)))
                elif name == "uuid":
                    query = query.filter(
                        func.REPLACE(cast(Simulation.uuid, String), "-", "").ilike(
                            "%{}%".format(value.replace("-", ""))
                        )
                    )
            elif query_type == QueryType.GT:
                if name == "creation_date":
                    query = query.filter(Simulation.datetime > date_time)
            elif query_type == QueryType.GE:
                if name == "creation_date":
                    query = query.filter(Simulation.datetime >= date_time)
            elif query_type == QueryType.LT:
                if name == "creation_date":
                    query = query.filter(Simulation.datetime < date_time)
            elif query_type == QueryType.LE:
                if name == "creation_date":
                    query = query.filter(Simulation.datetime <= date_time)
            elif query_type == QueryType.NE:
                if name == "creation_date":
                    query = query.filter(Simulation.datetime != date_time)
            elif name in ("uuid", "alias"):
                raise ValueError(f"Invalid query type {query_type} for alias or uuid.")

        names_filters = []
        for name, _, _ in constraints:
            if name in ("alias", "uuid", "creation_date"):
                continue
            names_filters.append(MetaData.element.ilike(name))
        if names_filters:
            query = query.filter(or_(*names_filters))
        
        return query

    def _get_sim_ids(
        self, constraints: List[Tuple[str, str, "QueryType"]]
    ) -> Iterable[int]:
        from ..query import query_compare, QueryType

        rows = self._get_metadata(constraints)

        sim_id_sets = {}
        for name, value, query_type in constraints:
            sim_id_sets[(name, value, query_type)] = set()

        for row in rows:
            for name, value, query_type in constraints:
                if name in ("alias", "uuid"):
                    sim_id_sets[(name, value, query_type)].add(row.simulation.id)
                if row.metadata.element == name:
                    if query_type == QueryType.EXIST:
                        sim_id_sets[(name, value, query_type)].add(row.simulation.id)
                    elif query_compare(query_type, name, row.metadata.value, value):
                        sim_id_sets[(name, value, query_type)].add(row.simulation.id)

        if sim_id_sets:
            return set.intersection(*sim_id_sets.values())

        return []

    def query_meta(
        self, constraints: List[Tuple[str, str, "QueryType"]]
    ) -> List["Simulation"]:
        """
        Query the metadata and return matching simulations.

        :return:
        """
        from .models.simulation import Simulation
        from sqlalchemy.orm import joinedload

        sim_ids = self._get_sim_ids(constraints)
        if not sim_ids:
            return []

        query = (
            self.session.query(Simulation)
            .options(joinedload(Simulation.meta))
            .filter(Simulation.id.in_(sim_ids))
        )
        return query.all()

    def query_meta_data(
        self,
        constraints: List[Tuple[str, str, "QueryType"]],
        meta_keys: List[str],
        limit: int = 0,
        page: int = 1,
        sort_by: str = "",
        sort_asc: bool = False,
    ) -> Tuple[int, List[dict]]:
        """
        Query the metadata and return matching simulations.

        :return:
        """
        from .models.simulation import Simulation
        from .models.metadata import MetaData
        from sqlalchemy.orm import Bundle
        from sqlalchemy import desc, asc, func

        sim_ids = self._get_sim_ids(constraints)
        if not sim_ids:
            return 0, []

        sort_query = None
        if sort_by:
            sort_dir = asc if sort_asc else desc
            sort_query = (
                self.session.query(
                    Simulation.id,
                    func.row_number()
                    .over(order_by=sort_dir(MetaData.value))
                    .label("row_num"),
                )
                .join(Simulation.meta)
                .filter(MetaData.element == sort_by)
                .subquery()
            )

        s_b = Bundle(
            "simulation",
            Simulation.id,
            Simulation.alias,
            Simulation.uuid,
            Simulation.datetime,
        )
        m_b = Bundle("metadata", MetaData.element, MetaData.value)
        if meta_keys:
            query = (
                self.session.query(s_b, m_b)
                .outerjoin(Simulation.meta)
                .filter(s_b.c.id.in_(sim_ids))
            )
            query = query.filter(m_b.c.element.in_(meta_keys))
        else:
            query = self.session.query(s_b).filter(s_b.c.id.in_(sim_ids))

        if sort_query is not None:
            query = query.join(sort_query, Simulation.id == sort_query.c.id).order_by(
                sort_query.c.row_num
            )

        return self._get_simulation_data(limit, query, meta_keys, page)

    def get_simulation(self, sim_ref: str) -> "Simulation":
        """
        Get the specified simulation from the database.

        :param sim_ref: The simulation UUID or alias.
        :return: The Simulation.
        """
        simulation = self._find_simulation(sim_ref)
        return simulation

    def get_simulation_parents(self, simulation: "Simulation") -> List[dict]:
        from .models.simulation import Simulation
        from .models.file import File

        subquery = (
            self.session.query(File.checksum)
            .filter(File.checksum != "")
            .filter(File.input_for.contains(simulation))
            .subquery()
        )
        query = (
            self.session.query(Simulation.uuid, Simulation.alias)
            .join(Simulation.outputs)
            .filter(File.checksum.in_(subquery))
            .filter(Simulation.alias != simulation.alias)
            .distinct()
        )
        return [{"uuid": r.uuid, "alias": r.alias} for r in query.all()]

    def get_simulation_children(self, simulation: "Simulation") -> List[dict]:
        from .models.simulation import Simulation
        from .models.file import File

        subquery = (
            self.session.query(File.checksum)
            .filter(File.checksum != "")
            .filter(File.output_of.contains(simulation))
            .subquery()
        )
        query = (
            self.session.query(Simulation.uuid, Simulation.alias)
            .join(Simulation.inputs)
            .filter(File.checksum.in_(subquery))
            .filter(Simulation.alias != simulation.alias)
            .distinct()
        )
        return [{"uuid": r.uuid, "alias": r.alias} for r in query.all()]

    def get_file(self, file_uuid_str: str) -> "File":
        """
        Get the specified file from the database.

        :param file_uuid_str: The string representation of the file UUID.
        :return: The File.
        """
        from .models.file import File

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

    def list_metadata_keys(self) -> List[dict]:
        from .models.metadata import MetaData

        if self.engine.dialect.name == "postgresql":
            query = self.session.query(MetaData.element, MetaData.value).distinct(
                MetaData.element
            )
        else:
            query = self.session.query(MetaData.element, MetaData.value).group_by(
                MetaData.element
            )
        return [{"name": row[0], "type": type(row[1]).__name__} for row in query.all()]

    def list_metadata_values(self, name: str) -> List[str]:
        from .models.metadata import MetaData
        from .models.simulation import Simulation
        from sqlalchemy import cast, String

        if name == "alias":
            query = (
                self.session.query(Simulation.alias)
                .filter(Simulation.alias != None)
            )
        elif name == "uuid":
            query = (
                self.session.query(cast(Simulation.uuid, String))
                .filter(Simulation.uuid != None)
            )
        else:
            query = (
                self.session.query(MetaData.value)
                .filter(MetaData.element == name)
                .distinct()
            )
        data = [row[0] for row in query.all()]
        try:
            return sorted(data)
        except TypeError:
            return data

    def insert_simulation(self, simulation: "Simulation") -> None:
        """
        Insert the given simulation into the database.

        :param simulation: The Simulation to insert.
        :return: None
        """
        from sqlalchemy.exc import DBAPIError, IntegrityError

        try:
            self.session.add(simulation)
            self.session.commit()
        except IntegrityError as err:
            self.session.rollback()
            if "alias" in str(err.orig):
                raise DatabaseError(
                    f"Simulation already exists with alias {simulation.alias} - please use a unique alias."
                )
            elif "uuid" in str(err.orig):
                raise DatabaseError(
                    f"Simulation already exists with uuid {simulation.uuid}."
                )
            raise DatabaseError(str(err.orig))
        except DBAPIError as err:
            self.session.rollback()
            raise DatabaseError(str(err.orig))

    def get_aliases(self, prefix: Optional[str]) -> List[str]:
        from .models.simulation import Simulation
        from sqlalchemy.sql import column

        if prefix:
            return [
                el[0]
                for el in self.session.query(Simulation)
                .filter(Simulation.alias.like(prefix + "%"))
                .values(column("alias"))
            ]
        else:
            return [
                el[0] for el in self.session.query(Simulation).values(column("alias"))
            ]


def get_local_db(config: Config) -> Database:
    import appdirs

    db_file = config.get_option(
        "db.file", default=os.path.join(appdirs.user_data_dir("simdb"), "sim.db")
    )
    db_dir = os.path.dirname(db_file)
    os.makedirs(db_dir, exist_ok=True)
    database = Database(Database.DBMS.SQLITE, file=db_file)
    return database
