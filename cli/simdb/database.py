import sqlite3
import uuid
from datetime import datetime

from . manifest import Manifest, Source


class Transaction:

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def __enter__(self) -> "Transaction":
        self.cursor = self.connection.cursor()
        self.cursor.execute("begin")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.cursor.execute("commit")
        else:
            self.cursor.execute("rollback")

    def insert(self, sql: str, *args, **kwargs) -> int:
        self.cursor.execute(sql, *args, **kwargs)
        return self.cursor.lastrowid


def create_uuid() -> uuid.UUID:
    return uuid.uuid3(uuid.NAMESPACE_DNS, "iter.org")


def insert_simulation(transaction: Transaction, sim_uuid: uuid.UUID) -> int:
    id = transaction.insert("""
    INSERT INTO simulations (current_datetime, simulation_uuid, status) VALUES (?, ?, ?, ?)
    """, datetime.now().isoformat(), sim_uuid.hex, "UNKNOWN")
    return id


def insert_file(transaction: Transaction, sim_id: int, file_uuid: uuid.UUID, input: Source) -> int:
    file_id = transaction.insert("""
    INSERT INTO files (access, checksum, current_datetime, directory, embargo, file_uuid, file_name, purpose, sensitivity, type, usage)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, "", input.checksum, datetime.now().isoformat(), "", "", file_uuid, input.name, "", "", input.type, "")
    transaction.insert("""
    INSERT INTO simulation_files (file, simulation) VALUES (?, ?)
    """, file_id, sim_id)
    return file_id


class Database:

    def __init__(self):
        self.connection = sqlite3.Connection("../sql/sim.db")
        self.connection.isolation_level = None

    def ingest(self, manifest: Manifest):
        with Transaction(self.connection) as transaction:
            sim_uuid = create_uuid()
            sim_id = insert_simulation(transaction, sim_uuid)
            for input in manifest.inputs:
                if input.type == Source.Type.PATH:
                    file_uuid = create_uuid()
                    insert_file(transaction, sim_id, file_uuid, input)
                    pass
                pass