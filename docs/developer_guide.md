# Developer Guide

## Setting up developer environment

Checking out develop branch of SimDB:

```bash
git clone https://github.com/iterorganization/SimDB.git
cd SimDB
git checkout develop
```

Create a virtual environment and install SimDB with all development dependencies
using the `dev` dependency group defined in `pyproject.toml`:

```bash
python3 -m venv venv --prompt SimDB
source venv/bin/activate
pip install -e . --group dev
```

You could also use [uv](https://docs.astral.sh/uv/getting-started/installation/) to install all dependencies:

```bash
uv sync
```


This installs SimDB along with all tools needed for testing, linting, type
checking, and running the server.

## Running the tests

In the SimDB root directory run:

```bash
pytest
```

## Running a development server

```bash
simdb_server
```

This will start a server on port 5000. You can test this server is running by opening http://localhost:5000 in a browser.

## Swagger API documentation

SimDB provides interactive Swagger API documentation for each API version. The documentation is automatically generated and accessible at different endpoints depending on the API version you want to explore.

### Accessing API documentation

- **v1.2 API**: http://localhost:5000/v1.2/docs
- **v1.2 API at ITER**: https://simdb.iter.org/scenarios/api/v1.2/docs

### API version differences

Each API version may have different endpoints and functionality:

- **v1.2**: Latest API with improved performance and additional features

Always check the appropriate version documentation for your use case.

## Linting and formatting

SimDB uses [Ruff](https://docs.astral.sh/ruff/) for both linting and code
formatting. Ruff replaces the previously used tools `flake8`, `pylint`, and
`black`. The Ruff configuration is defined in `pyproject.toml` under
`[tool.ruff]` and `[tool.ruff.lint]`.

To check formatting:

```bash
python -m ruff format --check
```

To auto-fix formatting:

```bash
python -m ruff format
```

To check linting:

```bash
python -m ruff check
```

To auto-fix linting issues where possible:

```bash
python -m ruff check --fix
```

## Type checking

SimDB uses [Ty](https://github.com/astral-sh/ty) for static type checking.

To run type checking:

```bash
python -m ty check src
```

## Continuous integration

The CI pipeline (defined in `.github/workflows/build_and_test.yml`) runs
automatically on every push and pull request. It tests against Python 3.11,
3.12, and 3.13, and runs the following checks in order:

1. **Formatting** – `ruff format --check`
2. **Linting** – `ruff check`
3. **Type checking** – `ty check src`
4. **Tests** – `pytest` with coverage reporting

Make sure all four checks pass locally before opening a pull request.

## Database migrations

SimDB uses [Alembic](https://alembic.sqlalchemy.org/) to manage database
schema migrations. Migration scripts live in the `alembic/versions/` directory.

### Configuration

Alembic is configured via `alembic.ini` in the project root. The database URL
is **not** stored in `alembic.ini`; instead it must be provided through the
`DATABASE_URL` environment variable:

```bash
export DATABASE_URL="postgresql+psycopg2://user:password@localhost/simdb"
```

For SQLite (e.g. during development):

```bash
export DATABASE_URL="sqlite:///simdb.db"
```

### Applying migrations

To upgrade the database to the latest schema revision:

```bash
alembic upgrade head
```

To upgrade to a specific revision:

```bash
alembic upgrade <revision_id>
```

To downgrade by one revision:

```bash
alembic downgrade -1
```

### Checking the current revision

```bash
alembic current
```

### Viewing migration history

```bash
alembic history --verbose
```

### Creating a new migration

After modifying the SQLAlchemy models, generate a new migration script
automatically with:

```bash
alembic revision --autogenerate -m "short description of change"
```

Review the generated file in `alembic/versions/` carefully before applying it,
as autogenerate may not capture every change (e.g. custom column types or
server defaults).

To apply the new migration:

```bash
alembic upgrade head
```

## Setting up PostgreSQL Database

This section will guide you through setting up a PostgreSQL server for SimDB.

Setup PostgreSQL configuration and data directory:

```bash
mkdir $HOME/Path/To/PostgresSQL_Data
```

Initialize database with data directory:

```bash
initdb -D $HOME/Path/To/PostgresSQL_Data -U simdb
```

Start database server:

```bash
pg_ctl -D $HOME/Path/To/PostgresSQL_Data/ -l logfile start
```

Verify database server status (should show `/tmp:5432 - accepting connections`):

```bash
pg_isready
```

Create a database named `simdb`:

```bash
createdb simdb -U simdb
```

Access database from command-line (will prompt `simdb=#`):

```bash
psql -U simdb
```

Set the `DATABASE_URL` environment variable and run migrations:

```bash
export DATABASE_URL="postgresql+psycopg2://simdb@localhost/simdb"
alembic upgrade head
```

Update the `[database]` section of `app.cfg`:

```
...

[database]
type = postgres
host = localhost
port = 5432

...
```
