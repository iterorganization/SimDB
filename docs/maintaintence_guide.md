# SimDB server maintenance guide

This guide describes the steps needed to set up and maintain a SimDB server as a production service. The first section details the general steps required to do this, followed by details on how this is done at ITER.

## Setting up SimDB as a service

### Installing SimDB

Create a virtual environment for SimDB:

```bash
python3 -m venv env_simdb
```

Then load the environment:

```bash
source env_simdb/bin/activate
```

Install SimDB using pip (replacing <TAG> with the latest release):

```bash
pip3 install git+ssh://git@git.iter.org/imex/simdb.git@<TAG>
```

Check where we need to put the config file by running:

```bash
python3 -c 'import appdirs; print(appdirs.user_config_dir("simdb"))'
```

Create this directory, i.e.:

```bash
mkdir -p /home/ITER/<username>/.config/simdb
```

Create a file `app.cfg` in this directory (see below for configuration file details):

```ini
DB_TYPE = "sqlite"
UPLOAD_FOLDER = "/home/ITER/<username>/simulations"
DEBUG = True
SSL_ENABLED = False
```

You can then test the server by running:

```bash
./scripts/simdb_server
```

This uses the Flask debug server so should not be used in production. Note that if another service is using port 5000 on the same machine then you will need to edit `simdb/remote/app.py` to change the port that the debug server runs on.

### SimDB Configuration File

#### Server configuration options

| Section | Option | Description |
| --- | --- | --- |
| DEFAULT | debug | |
| database | type | database type [sqlite, postgres] |
| database | file | database file (for sqlite) |
| database | host | database host (for postgres) |
| database | port | database port (for postgres) |
| database | name | database name (for postgres) |
| database | port | database port (for postgres) |
| server | upload_folder | |
| server | ssl_enabled | |
| server | ssl-enabled | |
| flask | flask_env | |
| flask | debug | |
| flask | testing | |
| flask | secret_key | | 
| validation | auto_validate | |
| validation | error_on_fail | |

#### Client configuration options

| Section | Option | Description |
| --- | --- | --- |
| remote | url | |
| remote | default | |

### Configuring nginx

### Creating system services

## Running SimDB at ITER

