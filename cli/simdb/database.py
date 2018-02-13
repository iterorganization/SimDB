import os
import sqlite3
import uuid
from datetime import datetime
from typing import Iterable, List, Dict, Optional, Tuple, Any

from .manifest import Manifest, Source


class DatabaseError(RuntimeError):
    pass


class Transaction:

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __enter__(self) -> "Transaction":
        self.cursor = self.connection.cursor()
        self.cursor.execute("begin")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.cursor.execute("commit")
        else:
            self.cursor.execute("rollback")

    def insert(self, sql: str, params: Iterable) -> int:
        self.cursor.execute(sql, params)
        return self.cursor.lastrowid

    def delete(self, sql: str, params: Iterable) -> bool:
        self.cursor.execute(sql, params)
        return self.cursor.rowcount


def create_uuid() -> uuid.UUID:
    return uuid.uuid1()


def insert_simulation(transaction: Transaction, sim_uuid: uuid.UUID, alias: Optional[str]) -> int:
    insert_sql = "INSERT INTO simulations (current_datetime, simulation_uuid, status, alias) VALUES (?, ?, ?, ?)"
    params = (datetime.now().isoformat(), sim_uuid.hex, "UNKNOWN", alias)
    sim_id = transaction.insert(insert_sql, params)
    return sim_id


def insert_file(transaction: Transaction, sim_id: int, file_uuid: uuid.UUID, input_source: Source) -> int:
    insert_sql = """
    INSERT INTO files (access, checksum, current_datetime, directory, embargo, file_uuid, file_name, purpose, sensitivity, type, usage)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params: Tuple = ("", input_source.checksum, datetime.now().isoformat(), "", "", file_uuid.hex, input_source.name, "", "", input_source.type.name, "")
    file_id = transaction.insert(insert_sql, params)

    insert_sql = "INSERT INTO simulation_files (file, simulation) VALUES (?, ?)"
    params = (file_id, sim_id)
    transaction.insert(insert_sql, params)
    return file_id


def list_simulations(connection: sqlite3.Connection) -> sqlite3.Cursor:
    list_sql = """
    SELECT * FROM simulations;
    """
    return connection.execute(list_sql)


def delete_simulation(transaction: Transaction, sim_uuid: uuid.UUID, sim_alias: str) -> None:
    if sim_uuid is not None:
        delete_sql = """
        DELETE FROM simulations WHERE simulation_uuid = ?
        """
        params = (sim_uuid.hex,)
    else:
        delete_sql = """
        DELETE FROM simulations WHERE alias = ?
        """
        params = (sim_alias,)
    if transaction.delete(delete_sql, params) == 0:
        raise DatabaseError("Failed to find simulation: " + (sim_uuid.hex if sim_uuid is not None else sim_alias))


def get_simulation(connection: sqlite3.Connection, sim_uuid: uuid.UUID, sim_alias: str) -> sqlite3.Cursor:
    get_sql = """
    SELECT * FROM simulations AS s
    """
    if sim_uuid is not None:
        get_sql += " WHERE simulation_uuid = ?"
        params = (sim_uuid.hex,)
    else:
        get_sql += " WHERE alias = ?"
        params = (sim_alias,)
    return connection.execute(get_sql, params)


def get_files(connection: sqlite3.Connection, sim_id: int) -> sqlite3.Cursor:
    get_sql = """
    SELECT f.* FROM files AS f, simulation_files sf WHERE sf.file = f.file_id AND sf.simulation = ?
    """
    params = (sim_id,)
    return connection.execute(get_sql, params)


def drop_db(connection: sqlite3.Connection) -> None:
    this_dir = os.path.dirname(os.path.realpath(__file__))
    sql_file = os.path.join(this_dir, "..", "..", "sql")
    with open(os.path.join(sql_file, "drop.sql")) as file:
        sql = file.readlines()
        connection.executescript(''.join(sql))


def create_db(connection: sqlite3.Connection) -> None:
    this_dir = os.path.dirname(os.path.realpath(__file__))
    sql_file = os.path.join(this_dir, "..", "..", "sql")
    with open(os.path.join(sql_file, "create.sql")) as file:
        sql = file.readlines()
        connection.executescript(''.join(sql))


class Database:

    def __init__(self):
        db_dir = os.path.join(os.environ["HOME"], ".simdb")
        os.makedirs(db_dir, exist_ok=True)
        db_file = os.path.join(db_dir, "sim.db")
        new_db = (not os.path.exists(db_file))
        self.connection = sqlite3.Connection(db_file)
        self.connection.row_factory = sqlite3.Row
        self.connection.isolation_level = None
        self.connection.execute("PRAGMA foreign_keys = ON;")
        if new_db:
            create_db(self.connection)

    def ingest(self, manifest: Manifest, alias: Optional[str]) -> None:
        with Transaction(self.connection) as transaction:
            sim_uuid = create_uuid()
            sim_id = insert_simulation(transaction, sim_uuid, alias)
            for input in manifest.inputs:
                if input.type == Source.Type.PATH:
                    file_uuid = create_uuid()
                    insert_file(transaction, sim_id, file_uuid, input)

    def reset(self) -> None:
        drop_db(self.connection)
        create_db(self.connection)

    def list(self) -> List[Dict]:
        return [dict(i) for i in list_simulations(self.connection)]

    def delete(self, sim_ref: str) -> None:
        sim_uuid = None
        sim_alias = None
        try:
            sim_uuid = uuid.UUID(sim_ref)
        except ValueError:
            sim_alias = sim_ref
        with Transaction(self.connection) as transaction:
            delete_simulation(transaction, sim_uuid, sim_alias)

    def get(self, sim_ref: str) -> dict:
        sim_uuid = None
        sim_alias = None
        try:
            sim_uuid = uuid.UUID(sim_ref)
        except ValueError:
            sim_alias = sim_ref
        row = get_simulation(self.connection, sim_uuid, sim_alias).fetchone()
        if row is None:
            raise DatabaseError("Failed to find simulation: " + (sim_uuid.hex if sim_uuid is not None else sim_alias))
        sim = dict(row)
        files = get_files(self.connection, int(sim["simulation_id"]))
        sim["files"] = [dict(i) for i in files]
        return sim
