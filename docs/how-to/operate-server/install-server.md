# Install a server

A SimDB server is the same package as the client, installed from source with
the server extras and given an `app.cfg`. Once you have it installed, see
[Run a development server](run-dev-server.md) and
[Run behind Nginx and Gunicorn](run-behind-nginx-gunicorn.md) for running it.

## Install

Clone SimDB and create a virtual environment:

```bash
git clone https://github.com/iterorganization/SimDB.git
cd SimDB
python3 -m venv venv
source venv/bin/activate
```

Install with the `all` extra (server, PostgreSQL, and IDS validation):

```bash
pip install -e ".[all]"
```

To install only what you need, combine the relevant
[extras](../../getting-started/installation.md#optional-extras), for example
`pip install -e ".[server,postgres]"`.

Verify:

```bash
simdb --version
```

## Create the server configuration

The server reads `app.cfg` from the application configuration directory. Find
it with:

```bash
dirname "$(simdb config path)"
```

On Linux this is typically `/home/$USER/.config/simdb`; on macOS,
`/Users/$USER/Library/Application Support/simdb`.

Create `app.cfg` there with the settings for your deployment, and set its
permissions to owner-only:

```bash
chmod 600 app.cfg
```

A minimal SQLite configuration:

```ini
[flask]
secret_key = CHANGE_ME_TO_A_LONG_RANDOM_STRING

[server]
upload_folder = /var/lib/simdb/simulations
admin_password = CHANGE_ME

[database]
type = sqlite

[authentication]
type = None
```

See the [server configuration reference](../../reference/server-configuration.md)
for every option, including authentication, validation, caching, email, and
roles, and for a PostgreSQL example.

```{tip}
To stand up a complete server (with PostgreSQL and Redis) in one command, use
the [Docker Compose deployment](run-with-docker.md) instead of installing by
hand.
```

## Deploy as a systemd service

The `Makefile` at the repository root automates the usual Docker Compose
deployment as a systemd unit: it installs the Compose files, the server
configuration and validation data under `/opt/simdb-server`, writes the unit
file and environment file, and wraps the `systemctl` calls. Run it from the
repository root, through `sudo` for anything that touches the system:

```bash
sudo make systemd-install   # copy files into place
sudo make systemd-enable    # daemon-reload and enable at boot
sudo make systemd-start     # start the service
```

Day-to-day control:

```bash
sudo make systemd-status
sudo make systemd-stop
sudo make systemd-disable   # stop and disable at boot
sudo make systemd-uninstall # stop/disable and print manual cleanup instructions
```

`systemd-uninstall` does not delete files. It stops and disables the service,
then prints the installed paths for you to review and remove manually.

`make help` prints the same list, and the Compose targets
(`up`, `down`, `logs-f`, `shell`, …) are available for running the stack without
installing a service. See
[Run with Docker Compose](run-with-docker.md) for what the stack contains.

### What gets installed

| Path | Contents |
| --- | --- |
| `/opt/simdb-server` | Compose files and validation data |
| `/opt/simdb-server/config/simdb.cfg` | The server's own settings: database, authentication, validation, caching |
| `/etc/simdb-server/simdb-server.env` | Which image and version runs, and how the container is launched: `APP_UID`/`APP_GID`, `SIMDB_UPLOAD_DIR`, Gunicorn (`docker/scripts/simdb-server.env.example` on first install) |
| `/etc/systemd/system/simdb-server.service` | The systemd unit |

The unit starts the stack from the installed Compose files, so the source
checkout is no longer needed once `systemd-install` has run. Database and Redis
state persist in the Compose named volumes and are not removed by
`systemd-uninstall`.

Only `simdb.cfg` and `simdb-server.env` are configuration; the rest is fixed by
the install. Neither requires rebuilding or re-pulling an image, and changing
either is followed by `sudo make systemd-start` (or
`systemctl restart simdb-server`). Nothing else on the host is part of the
configuration.

### Configure container environment

The unit already defaults to the published image, so a normal installation
needs no changes here. Review `/etc/simdb-server/simdb-server.env` before
starting the service and adjust it as needed: it selects the image and version,
and sets the Gunicorn runtime options. See
[docker/scripts/simdb-server.env.example](../../../docker/scripts/simdb-server.env.example)
for the available variables and example values.

The defaults are:

```bash
SIMDB_IMAGE=ghcr.io/iterorganization/simdb-server
SIMDB_TAG=latest
```

The unit never builds images, so whichever name it resolves to must already
exist locally or in the registry; the Compose-file default of
`simdb-server:local` is not produced automatically and would fail to start. To
run an image built from your checkout instead, build it with:

```bash
make service
```

And set the enviroment to use this image:tag :

```bash
# /etc/simdb-server/simdb-server.env
SIMDB_IMAGE=simdb-server
SIMDB_TAG=service
```

Images are published to `ghcr.io/iterorganization/simdb-server` by the
[Docker Image build and publish](https://github.com/iterorganization/SimDB/blob/develop/.github/workflows/docker_image.yml)
workflow:

| Tag | Published on |
| --- | --- |
| `latest` | every push to `main` |
| `develop` | every push to `develop` |
| `<version>` | every push to `develop`, and every tag push |

`<version>` is the version reported by `simdb --version` inside that image: the
tag name itself for a release (for example `0.15.2`), or a development version
such as `0.15.2.dev319` for a build between releases. In production, pin it
rather than tracking a moving tag:

```bash
# /etc/simdb-server/simdb-server.env
SIMDB_TAG=0.15.2
```

### Configure SimDB Server

The server itself is configured through the installed
`/opt/simdb-server/config/simdb.cfg`, exactly as described in
[Run with Docker Compose](run-with-docker.md#configure). The installed unit
expects `/opt/simdb-server` and `/etc/simdb-server/simdb-server.env`; use these
default paths for a live installation. `DESTDIR` can be used to stage files for
packaging or inspection, but a staged unit is not ready to run until installed
at those paths.

`systemd-install` also creates `/opt/simdb-server/upload_folder` with ownership
set to the container runtime UID/GID (`1000:1000` by default), because the web
container runs as a non-root user and writes uploads through a bind mount. This
is only the default location: set `SIMDB_UPLOAD_DIR` in
`/etc/simdb-server/simdb-server.env` to use another directory, an absolute path
or one relative to `/opt/simdb-server` (e.g. a network mount). The directory
must already exist and be writable by the same UID/GID the container runs as;
`systemd-install` only prepares the default path.

If you use different `APP_UID`/`APP_GID` values, set them both in the environment
file and pass the same values to the install step so the runtime identity and
host directory ownership match:

```bash
sudo make systemd-install APP_UID=1234 APP_GID=1234
```

```{tip}
To stage an installation without touching `/` — for packaging, or to inspect
what would be written — pass a prefix: `make systemd-install
DESTDIR=/tmp/simdb-staging`.
```

## Next steps

- [Run with Docker Compose](run-with-docker.md) for an all-in-one deployment.
- [Deploy as a systemd service](#deploy-as-a-systemd-service) to keep it running
  on a server.
- [Set up PostgreSQL](set-up-postgresql.md) for production.
- [Configure authentication](configure-authentication.md).
- [Configure validation](configure-validation.md).
- [Run behind Nginx and Gunicorn](run-behind-nginx-gunicorn.md) for production.
