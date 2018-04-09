import os
from inspect import getmembers, isfunction
import hashlib

from .database.database import Database


def inherit_docstrings(cls):
    for name, func in getmembers(cls, isfunction):
        if func.__doc__:
            continue
        for parent in cls.__mro__[1:]:
            if hasattr(parent, name):
                func.__doc__ = getattr(parent, name).__doc__.format(cls=cls)
    return cls


def format_docstring(cls):
    def decorator(func):
        func.__doc__ = func.__doc__.format(cls=cls)
        return func
    return decorator


def sha1_checksum(path: str) -> str:
    sha1 = hashlib.sha1()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha1.update(chunk)
    return sha1.hexdigest()


def get_local_db() -> Database:
    db_dir = os.path.join(os.environ["HOME"], ".simdb")
    os.makedirs(db_dir, exist_ok=True)
    db_file = os.path.join(db_dir, "sim.db")
    database = Database(Database.DBMS.SQLITE, file=db_file)
    return database
