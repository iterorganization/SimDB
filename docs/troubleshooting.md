# Troubleshooting

Common problems and how to resolve them. If your issue is not here, see
[Getting help](#getting-help).

## `command not found: simdb`

The install location's `bin` directory is not on your `PATH`.

- Activate the virtual environment you installed into
  (`source venv/bin/activate`), or
- add the pip script directory to your `PATH`.

See [Installation](getting-started/installation.md).

## Configuration file permission errors

On Linux and macOS the user config file must be readable only by you. If SimDB
complains about incorrect permissions:

```bash
chmod 600 "$(simdb config path)"
```

See [Client configuration](reference/configuration.md).

## Local database was set up by a newer version of SimDB

If you go back to an older SimDB (for example after trying a development
version), it cannot open a local database that the newer version has set up or
upgraded. Older releases such as 0.15.2 fail with
`(sqlite3.OperationalError) database is locked`; newer ones say the database was
set up by a newer version of SimDB.

Either upgrade SimDB again, or, to keep using the older version, replace the
local database. It lives in `~/.local/share/simdb/sim.db` on Linux and
`~/Library/Application Support/simdb/sim.db` on macOS, unless you set
`db.file` in your configuration.

- If SimDB upgraded an existing database, it saved a copy first in the
  `backups/` folder next to `sim.db`. Move `sim.db` aside and copy back the
  latest backup taken before the upgrade:

  ```bash
  cd ~/.local/share/simdb
  mv sim.db sim.db.newer
  cp backups/<date>.db sim.db
  ```

- If the newer version created the database from scratch, there is no backup.
  Move `sim.db` aside and SimDB will offer to create a new one.

## Cannot connect to a remote / SSL certificate errors

- Check the remote URL: `simdb remote config list`, then `simdb remote test`.
- On an ITER HPC node, install the ITER CA bundle and set
  `REQUESTS_CA_BUNDLE`. See [Connect to ITER](how-to/connect-to-iter.md).
- For remote IMAS data, make sure the data server's port is reachable through
  your firewall. Contact your system administrator if not.

## Authentication keeps prompting

If the server supports tokens, create one so you are not asked every time:

```bash
simdb remote token new
```

Servers behind an F5 firewall (including `simdb.iter.org`) do not support
tokens; you authenticate at the firewall each session. See
[Authenticate](how-to/authenticate.md).

## Validation fails

The two usual causes:

- **A data source is missing or its checksum changed** since ingestion. Restore
  the file or re-ingest from an updated manifest.
- **Required metadata is missing.** Check the server's requirements with
  `simdb remote schema -d 10` and add the fields.

See [Validate a simulation](how-to/validate-a-simulation.md).

## Cannot read MDSplus (AL4) data

SimDB reads Access Layer 5 (AL5) data or later. Migrate AL4 MDSplus data first.
See [Migrate AL4 MDSplus data](how-to/migrate-al4-mdsplus.md).

## Server will not start: port already in use

Another service is using port 5000. Stop it, or change the port. For the
built-in server set `[server] port` in `app.cfg`; behind Nginx/Gunicorn change
the bind address. See
[Run a development server](how-to/operate-server/run-dev-server.md).

## PostgreSQL connection refused

For a local database, check `pg_hba.conf` in the PostgreSQL data directory and
ensure the connection method is `trust` (or another you can authenticate with)
rather than `ident`. See
[Set up PostgreSQL](how-to/operate-server/set-up-postgresql.md).

## Getting help

- Open an issue on [GitHub](https://github.com/iterorganization/SimDB/issues).
- Browse the [reference](reference/cli.md) and
  [explanation](explanation/concepts.md) sections.
