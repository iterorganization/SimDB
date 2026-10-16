# Run with Docker Compose

SimDB ships a Docker Compose setup that runs the server together with its
PostgreSQL database and a Redis instance, applying database migrations
automatically. This is the quickest way to stand up a complete server.

## Prerequisites

- Docker and Docker Compose.
- A checkout of the SimDB repository (the `Dockerfile` and `docker-compose.yml`
  live at its root).

## Services

`docker-compose.yml` defines the following:

| Service | Role |
| --- | --- |
| `web` | The SimDB server, published on port 5000. |
| `postgres` | PostgreSQL database (user/password/db `simdb`). |
| `redis` | Redis, used as the message broker for background workers. |
| `migrations` | One-shot service that runs `alembic upgrade head`, then exits. |
| `worker`, `beat` | Optional Celery worker and scheduler (see [Background workers](#background-workers)). |

The image is built from the `Dockerfile`, which uses `uv` and installs SimDB
with the `all` extra.

## Configure

The server reads its configuration from `config/simdb.cfg`, which is mounted into
the container. The image sets `SIMDB_SITE_CONFIG_PATH=/app/config/simdb.cfg`, so
edit `config/simdb.cfg` to configure the deployment. A starting point:

```ini
[flask]
flask_env = development
debug = True
testing = True
secret_key = CHANGE_ME

[authentication]
type = None

[server]
upload_folder = /data/simdb/simulations
port = 5000
ssl_enabled = False
admin_password = CHANGE_ME
imas_remote_host = localhost
imas_remote_substitution = True

[database]
type = postgres
host = postgres
port = 5432
user = simdb
password = simdb
db_name = simdb

[validation]
path = ./validation
auto_validate = True
error_on_fail = True

[celery]
broker_url = redis://redis:6379/0
result_backend = redis://redis:6379/0

[partition]
data = /data/simdb/partition
```

Note that `[database].host` is `postgres` (the Compose service name) and the
Celery broker points at the `redis` service. The `[server].port` value must
match the published port.

See the [server configuration reference](../../reference/server-configuration.md)
for all options.

### Writable bind mounts

The runtime image drops privileges and runs as the `simdb` user. By default
that user is created with UID/GID `1000:1000` in the image. If you bind-mount a
host directory onto `upload_folder` (the Compose setup does this with
`./upload_folder:/data/simdb/simulations`), Docker uses the host directory's
existing ownership and mode bits. The container cannot fix that from inside the
mount.

In practice, the host directory must be writable by the same numeric UID/GID as
the container process before the container starts. For example:

```bash
sudo install -d -m 0775 -o 1000 -g 1000 ./upload_folder
```

Avoid world-writable workarounds such as `chmod a+rwX`. If you build your own
image with different `APP_UID`/`APP_GID` values, apply the same numeric
ownership to the host path.

### Gunicorn runtime

The `web` service runs Gunicorn with three `gthread` workers, four threads per
worker, and a 120-second request timeout by default. Override these settings
through the environment when starting Compose:

```bash
GUNICORN_WORKERS=4 GUNICORN_THREADS=8 GUNICORN_TIMEOUT=180 docker compose up --build
```

The available variables are `GUNICORN_BIND`, `GUNICORN_WORKERS`,
`GUNICORN_WORKER_CLASS`, `GUNICORN_THREADS`, and `GUNICORN_TIMEOUT`.

## Start

```bash
docker compose up --build
```

Compose builds the image, starts PostgreSQL and Redis, waits for them to become
healthy, runs the migrations, and then starts the `web` service. The server is
then reachable at <http://localhost:5000>.

To run in the background:

```bash
docker compose up --build -d
```

Stop everything with:

```bash
docker compose down
```

Database and Redis state persist in named volumes (`postgres_data`,
`redis_data`).

## Background workers

The `worker` and `beat` services run under the `with_workers`
[Compose profile](https://docs.docker.com/compose/profiles/), so they are off by
default. Enable them when you want asynchronous processing:

```bash
docker compose --profile with_workers up --build
```

They use the `[celery]` broker and result backend from `config/simdb.cfg`.

## Building against a different Python version

The image accepts a `PYVER` build argument, which selects the Python version
used as the build base; the default is 3.12:

```bash
docker build --build-arg PYVER=3.11 .
```
