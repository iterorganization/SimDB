# Developer Guide

## Setting up devloper environment

Checking out develop branch of SimDB:

```bash
git clone ssh://git@git.iter.org/imex/simdb.git
cd simdb
git checkout develop
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Installing server dependencies:

```bash
pip3 install -r requirements.txt
```

Installing editable version of SimDB:

```bash
pip3 install -e .
```

## Running the tests

In the SimDB root directory run:

```bash
pytest
```

## Running a development server

```bash
simdb_server
```

This will start a server on port 5000. You can test this server is running by opening htpp://localhost:5000 in a browser.

## Setting up PostgreSQL Database on local (SDCC)
This section will guide to setting up a PostgreSQL server for SimDB.

Load PostgreSQL module
```bash
module load PostgreSQL
``` 

Setup PostgreSQL configuration and data directory
```bash
mkdir $HOME/Path/To/PostgresSQL_Data
```

Initialize database with data directory
```bash
initdb -D $HOME/Path/To/PostgresSQL_Data -U simdb
```

Start database server
```bash
pg_ctl -D $HOME/Path/To/PostgresSQL_Data/ -l logfile start
```

Verify database server status and should prompt /tmp:5432 - accepting connections
```bash
pg_isready
```

Creates a database named simdb
```bash
createdb simdb -U simdb
```

Access database from command-line. It will prompt simdb=#
```bash
psql -U simdb
```

Update [database] section of app.cfg
```
...

[database]
type = postgres
host = localhost
port = 5432

...
```
For more information, please refer [How to setup PostgreSQL on SDCC](https://confluence.iter.org/display/IMP/How+to+setup+PostgreSQL+on+SDCC) 