# Run database migrations

SimDB manages its database schema with [Alembic](https://alembic.sqlalchemy.org/).
Migration scripts live in `src/simdb/database/migrations/versions/`.

## Configure the database URL

Alembic is configured by `alembic.ini` in the project root, but the database URL
is **not** stored there. Provide it through the `DATABASE_URL` environment
variable.

PostgreSQL:

```bash
export DATABASE_URL="postgresql+psycopg2://user:password@localhost/simdb"
```

SQLite (for development):

```bash
export DATABASE_URL="sqlite:///simdb.db"
```

## Apply migrations

```bash
alembic upgrade head          # upgrade to the latest revision
alembic upgrade <revision>    # upgrade to a specific revision
alembic downgrade -1          # downgrade one revision
```

## Inspect state

```bash
alembic current               # current revision
alembic history --verbose     # full history
```

## Create a migration

After changing the SQLAlchemy models, autogenerate a migration:

```bash
alembic revision --autogenerate -m "short description of change"
```

Review the generated script in `src/simdb/database/migrations/versions/` carefully before applying it.
Autogenerate may miss some changes, such as custom column types or server
defaults. Then apply it:

```bash
alembic upgrade head
```
