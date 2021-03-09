# -*- coding: utf-8 -*-
"""Database module.

The database module contains the code for creating and interacting with the database. Using SQLAlchemy the code can be
used with various types of databases including SQLite and PostgreSQL.
"""

from .database import Database, DatabaseError, get_local_db
