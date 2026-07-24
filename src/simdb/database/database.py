import contextlib
import json
import shutil
import sys
import uuid
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, cast

import appdirs
import sqlalchemy.orm
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from rich.prompt import Confirm
from sqlalchemy import Float, String, Text, create_engine, func, text
from sqlalchemy import and_ as sql_and
from sqlalchemy import cast as sql_cast
from sqlalchemy import or_ as sql_or
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import elements

from simdb.config import Config
from simdb.json import CustomDecoder, CustomEncoder
from simdb.query import QueryType
from simdb.remote.models import SimulationReference

from .models import Base
from .models.file import File
from .models.simulation import Simulation

_ALEMBIC_INI = Path("alembic.ini")


class DatabaseError(RuntimeError):
    pass


class DatabaseUninitializedError(DatabaseError):
    pass


class DatabaseOutdatedError(DatabaseError):
    pass


def check_migrations(engine) -> str:
    """Check that the database is up-to-date with the latest Alembic migration.

    Raises :class:`DatabaseUninitializedError` if the database has not been
    initialised at all (i.e. the ``alembic_version`` table is absent), or
    :class:`DatabaseOutdatedError` if the database schema is behind the head
    revision.
    """
    alembic_cfg = AlembicConfig(str(_ALEMBIC_INI))
    script = ScriptDirectory.from_config(alembic_cfg)
    head_revision = script.get_current_head()

    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_revision = context.get_current_revision()

    if current_revision is None:
        raise DatabaseUninitializedError(
            "The database has not been initialised. "
            f"Run 'DATABASE_URL={engine.url} alembic upgrade head' before starting the "
            "server. "
        )

    if current_revision != head_revision:
        raise DatabaseOutdatedError(
            f"Database schema is out of date: current revision is {current_revision}, "
            f"but the latest revision is {head_revision}. "
            f"Run 'DATABASE_URL={engine.url} alembic upgrade head' to apply pending "
            "migrations. "
        )
    return current_revision


def run_migrations(engine) -> None:
    """Run the database migrations."""
    config = AlembicConfig(_ALEMBIC_INI)
    config.set_main_option("script_location", "alembic")
    script = ScriptDirectory.from_config(config)

    def upgrade(rev, context):
        return script._upgrade_revs("head", rev)

    with engine.connect() as conn:
        context = MigrationContext.configure(
            conn, opts={"target_metadata": Base.metadata, "fn": upgrade}
        )

        with context.begin_transaction(), Operations.context(context):
            context.run_migrations()


TYPING = TYPE_CHECKING or "sphinx" in sys.modules

if TYPING:
    # Only importing these for type checking and documentation generation in order to
    # speed up runtime startup.
    import sqlalchemy
    from sqlalchemy.orm import scoped_session

    from simdb.query import QueryType

    from .models import Base
    from .models.file import File
    from .models.simulation import Simulation
    from .models.watcher import Watcher

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

        def execute(self, query: Any, *args, **kwargs) -> Any:
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
    _session: Optional["sqlalchemy.orm.scoped_session"] = None

    class DBMS(Enum):
        """
        DBMSs supported.
        """

        SQLITE = auto()
        POSTGRESQL = auto()
        MSSQL = auto()

    def __init__(self, db_type: DBMS, scopefunc=None, **kwargs) -> None:
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

            self.engine: sqlalchemy.engine.Engine = create_engine(
                "sqlite:///{file}".format(**kwargs),
                json_serializer=lambda obj: json.dumps(obj, cls=CustomEncoder),
                json_deserializer=lambda s: json.loads(s, cls=CustomDecoder),
            )

        elif db_type == Database.DBMS.POSTGRESQL:
            if "host" not in kwargs:
                raise ValueError("Missing host parameter for POSTGRESQL database")
            if "port" not in kwargs:
                raise ValueError("Missing port parameter for POSTGRESQL database")
            kwargs.setdefault("user", "simdb")
            kwargs.setdefault("password", "simdb")
            kwargs.setdefault("db_name", "simdb")

            self.engine: sqlalchemy.engine.Engine = create_engine(
                "postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}".format(
                    **kwargs
                ),
                pool_size=25,
                max_overflow=50,
                pool_pre_ping=True,
                pool_recycle=3600,
                json_serializer=lambda obj: json.dumps(obj, cls=CustomEncoder),
                json_deserializer=lambda s: json.loads(s, cls=CustomDecoder),
            )

        elif db_type == Database.DBMS.MSSQL:
            if "user" not in kwargs:
                raise ValueError("Missing user parameter for MSSQL database")
            if "password" not in kwargs:
                raise ValueError("Missing password parameter for MSSQL database")
            if "dsnname" not in kwargs:
                raise ValueError("Missing dsnname parameter for MSSQL database")
            self.engine: sqlalchemy.engine.Engine = create_engine(
                "mssql+pyodbc://{user}:{password}@{dsnname}".format(**kwargs)
            )

        else:
            raise ValueError("Unknown database type: " + db_type.name)

        Base.metadata.bind = self.engine
        if scopefunc is None:

            def scopefunc():
                return 0

        self.session: Session = cast(
            "Session",
            scoped_session(sessionmaker(bind=self.engine), scopefunc=scopefunc),
        )

    def close(self):
        """Close the database session and dispose of the engine."""
        if hasattr(self, "session"):
            self.session.remove()  # For scoped_session
        if hasattr(self, "engine"):
            self.engine.dispose()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _get_simulation_data(
        self, query, meta_keys, limit, page, sort_by="", sort_asc=False
    ) -> Tuple[int, List]:
        """
        Build simulation data from query results with JSON metadata.

        :param query: SQLAlchemy query object
        :param meta_keys: List of metadata keys to include
        :param limit: Maximum number of results per page
        :param page: Page number (1-indexed)
        :param sort_by: Field name to sort by (can be alias/uuid/datetime/metadata key)
        :param sort_asc: Sort in ascending order if True, descending if False
        :return: Tuple of (total_count, list of simulation dicts)
        """
        total_count = query.count()

        if sort_by:
            query = self._apply_sort_by(query, sort_by, sort_asc)

        if limit:
            offset = (page - 1) * limit
            query = query.limit(limit).offset(offset)

        all_rows = query.all()

        results = []
        for row in all_rows:
            sim_data = {
                "alias": row.alias,
                "uuid": row.uuid,
                "datetime": row.datetime.isoformat(),
            }

            meta_dict = row._metadata or {}

            sim_data["_meta_dict"] = meta_dict

            if meta_keys:
                sim_data["metadata"] = [
                    {"element": k, "value": v}
                    for k, v in meta_dict.items()
                    if k in meta_keys
                ]

            results.append(sim_data)

        for sim_data in results:
            sim_data.pop("_meta_dict", None)

        return total_count, results

    def _apply_sort_by(self, query, sort_by: str, sort_asc: bool):
        """
        Apply ORDER BY clause to query for given sort field.

        :param query: SQLAlchemy query object
        :param sort_by: Field name to sort by
        :param sort_asc: Sort in ascending order if True, descending if False
        :return: Query with ORDER BY applied
        """
        dialect = self.engine.dialect.name

        if sort_by == "alias":
            return query.order_by(
                Simulation.alias if sort_asc else Simulation.alias.desc()
            )
        elif sort_by == "uuid":
            return query.order_by(
                Simulation.uuid if sort_asc else Simulation.uuid.desc()
            )
        elif sort_by == "datetime":
            return query.order_by(
                Simulation.datetime if sort_asc else Simulation.datetime.desc()
            )
        else:
            sort_col = self._get_json_sort_column(sort_by, dialect)
            if sort_col is not None:
                return query.order_by(sort_col if sort_asc else sort_col.desc())
        return query

    def _get_json_sort_column(self, key: str, dialect: str):
        """
        Get SQLAlchemy column expression for sorting by JSON metadata key.

        :param key: Metadata key to sort by
        :param dialect: Database dialect name
        :return: Column expression for ORDER BY
        """
        sort_exprs = {
            "postgresql": Simulation._metadata.op("->>")(key),
            "sqlite": func.json_extract(Simulation._metadata, f'$."{key}"'),
        }
        return sort_exprs.get(dialect)

    def _find_simulation(self, sim_ref: str) -> "Simulation":
        try:
            sim_uuid = uuid.UUID(sim_ref)
            simulation = (
                self.session.query(Simulation).filter_by(uuid=sim_uuid).one_or_none()
            )
        except ValueError:
            try:
                simulation = (
                    self.session.query(Simulation)
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
            raise DatabaseError(f"Simulation {sim_ref} not found.") from None
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

        with contextlib.closing(self.engine.connect()) as con:
            trans = con.begin()
            for table in reversed(Base.metadata.sorted_tables):
                con.execute(table.delete())
            trans.commit()

    def list_simulations(
        self, meta_keys: Optional[List[str]] = None, limit: int = 0
    ) -> List["Simulation"]:
        """
        Return a list of all the simulations stored in the database.

        :return: A list of Simulations.
        """
        query = self.session.query(Simulation)
        if limit:
            query = query.limit(limit)
        return query.all()

    def list_simulation_data(
        self,
        meta_keys: Optional[List[str]] = None,
        limit: int = 0,
        page: int = 1,
        sort_by: str = "",
        sort_asc: bool = False,
    ) -> Tuple[int, List[dict]]:
        """
        Return a list of all the simulations stored in the database.

        :return: A tuple of (total_count, list of simulation data dicts).
        """
        query = self.session.query(Simulation)

        return self._get_simulation_data(
            query, meta_keys, limit, page, sort_by, sort_asc
        )

    def get_simulation_data(self, query):
        limit_query = query
        return limit_query

    def list_files(self) -> List["File"]:
        """
        Return a list of all the files stored in the database.

        :return:  A list of Files.
        """

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

    def _build_json_filter(
        self,
        column: Any,
        key: str,
        query_type: "QueryType",
        compare_value: str,
    ) -> Optional[elements.BinaryExpression]:
        dialect = self.engine.dialect.name

        if dialect == "postgresql":
            json_obj = column.op("->")(key)
            json_access = column.op("->>")(key)
            json_min = column.op("->")(key).op("->>")("min")
            json_max = column.op("->")(key).op("->>")("max")
        elif dialect == "sqlite":
            json_obj = func.json_extract(column, f'$."{key}"')
            json_access = func.json_extract(column, f'$."{key}"')
            json_min = func.json_extract(column, f'$."{key}".min')
            json_max = func.json_extract(column, f'$."{key}".max')
        else:
            return None

        try:
            cmp_float = float(compare_value)
        except ValueError:
            cmp_float = None

        def _string_cmp(op):
            if dialect == "postgresql":
                return op(json_access, compare_value)
            return op(func.cast(json_access, String), compare_value)

        def _number_cmp(cmp_op):
            if dialect == "postgresql":
                return sql_and(
                    func.jsonb_typeof(json_obj) == "number",
                    cmp_op(),
                )
            return sql_and(
                func.json_type(func.json_extract(column, f'$."{key}"')).in_(
                    ["integer", "real"]
                ),
                cmp_op(),
            )

        def _num_with_op(cmp_op):
            if cmp_float is None:
                return None
            return _number_cmp(cmp_op)

        if query_type == QueryType.EQ:
            return _string_cmp(lambda a, b: a == b)
        elif query_type == QueryType.NE:
            return _string_cmp(lambda a, b: a != b)
        elif query_type == QueryType.IN:
            return _string_cmp(lambda a, b: a.ilike(f"%{b}%"))
        elif query_type == QueryType.NI:
            return _string_cmp(lambda a, b: a.notilike(f"%{b}%"))
        elif query_type == QueryType.GT:
            return _num_with_op(lambda: sql_cast(json_access, Float) > cmp_float)
        elif query_type == QueryType.GE:
            return _num_with_op(lambda: sql_cast(json_access, Float) >= cmp_float)
        elif query_type == QueryType.LT:
            return _num_with_op(lambda: sql_cast(json_access, Float) < cmp_float)
        elif query_type == QueryType.LE:
            return _num_with_op(lambda: sql_cast(json_access, Float) <= cmp_float)
        elif query_type == QueryType.AGT:
            if cmp_float is not None:
                return sql_cast(json_max, Float) > cmp_float
        elif query_type == QueryType.AGE:
            if cmp_float is not None:
                return sql_cast(json_max, Float) >= cmp_float
        elif query_type == QueryType.ALT:
            if cmp_float is not None:
                return sql_cast(json_min, Float) < cmp_float
        elif query_type == QueryType.ALE and cmp_float is not None:
            return sql_cast(json_min, Float) <= cmp_float

        return None

    def _build_json_query(self, constraints: List[Tuple[str, str, "QueryType"]]) -> Any:
        if not constraints:
            return self.session.query(Simulation)

        query = self.session.query(Simulation)

        for name, value, query_type in constraints:
            if name == "alias":
                v = value
                alias_filters = {
                    QueryType.EQ: lambda v=v: func.lower(Simulation.alias) == v.lower(),
                    QueryType.IN: lambda v=v: Simulation.alias.ilike(f"%{v}%"),
                    QueryType.NI: lambda v=v: Simulation.alias.notilike(f"%{v}%"),
                    QueryType.NE: lambda v=v: func.lower(Simulation.alias) != v.lower(),
                    QueryType.EXIST: lambda: Simulation.alias.isnot(None),
                }
                filter_fn = alias_filters.get(query_type)
                if filter_fn:
                    query = query.filter(filter_fn())
            elif name == "uuid":
                v = value
                uuid_filters = {
                    QueryType.EQ: lambda v=v: Simulation.uuid == uuid.UUID(v),
                    QueryType.IN: lambda v=v: func.REPLACE(
                        sql_cast(Simulation.uuid, String), "-", ""
                    ).ilike(f"%{v.replace('-', '')}%"),
                    QueryType.NI: lambda v=v: func.REPLACE(
                        sql_cast(Simulation.uuid, String), "-", ""
                    ).notilike(f"%{v.replace('-', '')}%"),
                    QueryType.NE: lambda v=v: Simulation.uuid != uuid.UUID(v),
                    QueryType.EXIST: lambda: Simulation.uuid.isnot(None),
                }
                filter_fn = uuid_filters.get(query_type)
                if filter_fn:
                    query = query.filter(filter_fn())
            elif name == "creation_date":
                date_time = datetime.strptime(
                    value.replace("_", ":"), "%Y-%m-%d %H:%M:%S"
                )
                dt_filters = {
                    QueryType.EQ: Simulation.datetime == date_time,
                    QueryType.GT: Simulation.datetime > date_time,
                    QueryType.GE: Simulation.datetime >= date_time,
                    QueryType.LT: Simulation.datetime < date_time,
                    QueryType.LE: Simulation.datetime <= date_time,
                    QueryType.NE: Simulation.datetime != date_time,
                    QueryType.EXIST: Simulation.datetime.isnot(None),
                }
                filter_expr = dt_filters.get(query_type)
                if filter_expr:
                    query = query.filter(filter_expr)
            else:
                if query_type == QueryType.EXIST:
                    dialect = self.engine.dialect.name
                    if dialect == "sqlite":
                        exist_filter = func.json_extract(
                            Simulation._metadata, f'$."{name}"'
                        ).isnot(None)
                    else:
                        exist_filter = Simulation._metadata.op("->>")(name).isnot(None)
                    query = query.filter(exist_filter)
                else:
                    meta_filter = self._build_json_filter(
                        Simulation._metadata,
                        name,
                        query_type,
                        value,
                    )
                    if meta_filter is not None:
                        query = query.filter(meta_filter)

        return query

    def query_meta(
        self, constraints: List[Tuple[str, str, "QueryType"]]
    ) -> List["Simulation"]:
        """
        Query the metadata and return matching simulations.

        :return:
        """
        query = self._build_json_query(constraints)
        result = query.all()
        return result

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
        query = self._build_json_query(constraints)
        result = self._get_simulation_data(
            query, meta_keys, limit, page, sort_by, sort_asc
        )
        return result

    def get_simulation(self, sim_ref: str) -> "Simulation":
        """
        Get the specified simulation from the database.

        :param sim_ref: The simulation UUID or alias.
        :return: The Simulation.
        """
        simulation = self._find_simulation(sim_ref)
        return simulation

    def get_simulation_parents(self, simulation: "Simulation") -> List[dict]:
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

    def get_simulation_parents_ref(
        self, simulation: "Simulation"
    ) -> List[SimulationReference]:
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
        return [SimulationReference(uuid=r.uuid, alias=r.alias) for r in query.all()]

    def get_simulation_children(self, simulation: "Simulation") -> List[dict]:
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

    def get_simulation_children_ref(
        self, simulation: "Simulation"
    ) -> List[SimulationReference]:
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
        return [SimulationReference(uuid=r.uuid, alias=r.alias) for r in query.all()]

    def get_file(self, file_uuid_str: str) -> "File":
        """
        Get the specified file from the database.

        :param file_uuid_str: The string representation of the file UUID.
        :return: The File.
        """

        try:
            file_uuid = uuid.UUID(file_uuid_str)
            file = self.session.query(File).filter_by(uuid=file_uuid).one_or_none()
        except ValueError as err:
            raise DatabaseError(f"Invalid UUID {file_uuid_str}.") from err
        if file is None:
            raise DatabaseError(f"Failed to find file {file_uuid.hex}.")
        self.session.commit()
        return file

    def get_metadata(self, sim_ref: str, name: str) -> List[str]:
        """
        Get all the metadata for the given simulation with the given key.

        :param sim_ref: the simulation identifier
        :param name: the metadata key
        :return: The matching metadata values.
        """
        simulation = self._find_simulation(sim_ref)
        self.session.commit()
        return simulation.find_meta(name)

    def add_watcher(self, sim_ref: str, watcher: "Watcher"):
        sim = self._find_simulation(sim_ref)
        sim.watchers.append(watcher)
        self.session.commit()

    def remove_watcher(self, sim_ref: str, username: str):
        sim = self._find_simulation(sim_ref)
        watchers = [w for w in sim.watchers if w.username == username]
        if not watchers:
            raise DatabaseError(f"Watcher not found for simulation {sim_ref}.")
        for watcher in watchers:
            sim.watchers.remove(watcher)
        self.session.commit()

    def list_watchers(self, sim_ref: str) -> List["Watcher"]:
        return self._find_simulation(sim_ref).watchers

    def list_metadata_keys(self) -> List[dict]:
        dialect = self.engine.dialect.name
        if dialect == "postgresql":
            result = self.session.execute(
                text("""
                    SELECT DISTINCT j.key,
                           CASE
                             WHEN j.value ? 'min' AND j.value ? 'max' THEN 'Range'
                             ELSE jsonb_typeof(j.value)::text
                           END as value_type
                    FROM simulations, jsonb_each(metadata) AS j
                """)
            ).fetchall()
            return [{"name": row[0], "type": row[1]} for row in result]
        else:
            result = self.session.execute(
                text("""
                    SELECT DISTINCT j.key, j.value
                    FROM simulations, json_each(simulations.metadata) AS j
                """)
            ).fetchall()
            type_map = {}
            for row in result:
                key, value = row
                if value in ("null", None):
                    continue
                try:
                    parsed = json.loads(value) if isinstance(value, str) else value
                    if isinstance(parsed, dict) and "min" in parsed and "max" in parsed:
                        type_map[key] = "Range"
                    elif isinstance(parsed, dict):
                        type_map[key] = "Object"
                    else:
                        type_map[key] = type(parsed).__name__
                except (json.JSONDecodeError, TypeError):
                    type_map[key] = "String"
            return [{"name": k, "type": v} for k, v in type_map.items()]

    def list_metadata_values(self, name: str) -> List[str]:
        if name == "alias":
            query = self.session.query(Simulation.alias).filter(
                Simulation.alias.isnot(None)
            )
            data = [row[0] for row in query.all()]
        else:
            dialect = self.engine.dialect.name
            if dialect == "postgresql":
                result = self.session.execute(
                    text("""
                        SELECT DISTINCT j.value
                        FROM simulations, jsonb_each_text(metadata) AS j
                        WHERE j.key = :key AND j.value IS NOT NULL
                    """),
                    {"key": name},
                ).fetchall()
                data = [row[0] for row in result]
            else:
                result = self.session.execute(
                    text("""
                        SELECT DISTINCT j.value
                        FROM simulations, json_each(simulations.metadata) AS j
                        WHERE j.key = :key AND j.value IS NOT NULL
                    """),
                    {"key": name},
                ).fetchall()
                data = []
                for row in result:
                    try:
                        parsed = (
                            json.loads(row[0]) if isinstance(row[0], str) else row[0]
                        )
                        data.append(parsed)
                    except (json.JSONDecodeError, TypeError):
                        data.append(row[0])

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

        try:
            self.session.add(simulation)
            self.session.commit()
        except IntegrityError as err:
            self.session.rollback()
            if "alias" in str(err.orig):
                raise DatabaseError(
                    f"Simulation already exists with alias {simulation.alias} - please "
                    "use a unique alias."
                ) from err
            elif "uuid" in str(err.orig):
                raise DatabaseError(
                    f"Simulation already exists with uuid {simulation.uuid}."
                ) from err
            raise DatabaseError(str(err.orig)) from err
        except DBAPIError as err:
            self.session.rollback()
            raise DatabaseError(str(err.orig)) from err

    def get_aliases(self, prefix: Optional[str]) -> List[str]:
        if prefix:
            query = self.session.query(Simulation.alias).filter(
                Simulation.alias.ilike(prefix + "%")
            )
            return [alias for (alias,) in query.all()]
        else:
            query = self.session.query(Simulation.alias)
            return [alias for (alias,) in query.all()]


def get_local_db(config: Config) -> Database:
    db_file = Path(
        config.get_string_option("db.file", default=None)
        or f"{appdirs.user_data_dir('simdb')}/sim.db"
    )
    db_file.parent.mkdir(parents=True, exist_ok=True)
    database = Database(Database.DBMS.SQLITE, file=db_file)
    try:
        check_migrations(database.engine)
    except DatabaseUninitializedError as e:
        if Confirm.ask("Local database has not been initialized. Initialize now?"):
            run_migrations(database.engine)
        else:
            raise e
    except DatabaseOutdatedError as e:
        if Confirm.ask("Local database schema is out of date. Run migrations now?"):
            backup_local_db(config)
            run_migrations(database.engine)
        else:
            raise e
    return database


def backup_local_db(config: Config):
    db_file = Path(
        config.get_string_option("db.file", default=None)
        or f"{appdirs.user_data_dir('simdb')}/sim.db"
    )
    if not db_file.exists():
        print("[warning]: No current database found, skipping backup.")

    db_backups = db_file.parent / "backups"
    db_backups.mkdir(parents=True, exist_ok=True)

    db_backup_file = db_backups / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
    shutil.copyfile(db_file, db_backup_file)
    print(f"Stored database backup in: {db_backup_file}")
