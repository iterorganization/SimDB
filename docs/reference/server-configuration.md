# Server configuration

A SimDB server reads its settings from an INI-style file named `app.cfg` in the
application configuration directory. Find that directory with:

```bash
dirname "$(simdb config path)"
```

The file must have `0600` permissions (owner read/write only), because it
contains secrets such as the admin password and Flask secret key.

This page is the reference for every `app.cfg` option. For task-oriented setup,
see the [Operating a server](../how-to/operate-server/install-server.md) guides.

## `[database]`

| Option | Required | Description |
| --- | --- | --- |
| `type` | Yes | Database type: `sqlite` or `postgres`. |
| `file` | If `type=sqlite` | SQLite database file. Defaults to `remote.db` in the user data directory. |
| `host` | If `type=postgres` | Database host. |
| `port` | If `type=postgres` | Database port. |
| `user` | No | Database user. Defaults to `simdb`. |
| `password` | No | Database password. Defaults to `simdb`. |
| `db_name` | No | Database name. Defaults to `simdb`. |

See [Set up PostgreSQL](../how-to/operate-server/set-up-postgresql.md).

## `[server]`

| Option | Required | Description |
| --- | --- | --- |
| `upload_folder` | Yes | Root directory where simulation files are stored. |
| `admin_password` | Yes | Password for the `admin` superuser. |
| `port` | No | Port the built-in server listens on. Defaults to 5000. |
| `ssl_enabled` | No | `True`/`False`: whether the built-in server uses SSL. Set `False` behind a dedicated web server. Defaults to `False`. |
| `ssl_cert_file` | If `ssl_enabled=True` | Path to the SSL certificate file. |
| `ssl_key_file` | If `ssl_enabled=True` | Path to the SSL key file. |
| `token_lifetime` | No | Days that generated tokens stay valid. Defaults to 30. |
| `imas_remote_host` | No | Host set on ingested IMAS URIs so data can be fetched via an IMAS remote access server. For example `imas:hdf5?path=foo` becomes `imas://<imas_remote_host>:<imas_remote_port>/uda?path=foo&backend=hdf5` on ingest. |
| `imas_remote_port` | No | Port set on ingested IMAS URIs. See `imas_remote_host`. |
| `copy_files` | No | `True`/`False`: copy uploaded data files into the server's storage. Defaults to `True`. |
| `copy_ids` | No | `True`/`False`: copy uploaded IMAS IDS data into the server's storage. Defaults to `True`. |
| `user_upload_folder` | No | Optional staging directory clients upload into before ingest (returned by the `staging_dir` endpoint). Falls back to `upload_folder` if unset. |
| `max_append_size` | No | Maximum size in bytes of a single resumable-upload chunk, advertised to clients via the `Upload-Limit` header. Defaults to `8388608` (8 MiB). Lower it to fit a reverse proxy's request body limit. |

## `[flask]`

| Option | Required | Description |
| --- | --- | --- |
| `secret_key` | Yes | Key used to sign server messages and authentication tokens. Use at least 20 characters. |
| `flask_env` | No | `development` or `production`. Defaults to `production`. |
| `debug` | No | `True`/`False`. Defaults to `True` when `flask_env=development`, otherwise `False`. |
| `testing` | No | `True`/`False`: propagate exceptions instead of handling them. Defaults to `False`. |
| `swagger_ui_doc_expansion` | No | Default Swagger UI state: `none`, `list`, or `full`. |

## `[validation]`

| Option | Required | Description |
| --- | --- | --- |
| `auto_validate` | No | `True`/`False`: run validation on uploaded simulations automatically. Defaults to `False`. |
| `error_on_fail` | No | `True`/`False`: reject simulations that fail validation. Requires `auto_validate=True`. Defaults to `False`. |

## `[file_validation]`

Options for validating the contents of simulation data files. Currently only
the `ids_validator` is available. See
[Configure validation](../how-to/operate-server/configure-validation.md).

| Option | Required | Description |
| --- | --- | --- |
| `type` | No | Name of the file validator, for example `ids_validator`. |
| `extra_rule_dirs` | For `ids_validator` | Comma-separated directories containing extra rulesets. |
| `rulesets` | For `ids_validator` | Comma-separated ruleset names to apply. |
| `bundled_ruleset` | For `ids_validator` | `True`/`False`: load rulesets bundled with `ids_validator`. Defaults to `True`. |
| `apply_generic` | For `ids_validator` | `True`/`False`: apply generic rulesets. Defaults to `True`. |
| `rule_filter_name` | For `ids_validator` | Only apply rulesets whose names match these comma-separated values. |
| `rule_filter_ids` | For `ids_validator` | Only apply rulesets for these comma-separated IDS names. |

## `[email]`

Outgoing SMTP server used to send watcher notifications.

| Option | Required | Description |
| --- | --- | --- |
| `server` | Yes | SMTP server hostname. |
| `port` | Yes | SMTP server port. |
| `user` | Yes | SMTP user to send mail from. |
| `password` | Yes | SMTP user password. |

## `[authentication]`

| Option | Required | Description |
| --- | --- | --- |
| `type` | Yes | Authentication method(s): `ActiveDirectory`, `LDAP`, `KeyCloak`, or `None`. List several separated by commas to enable more than one; a token authenticator is always available in addition. |
| `firewall_auth` | No | `True`/`False`: read authentication from firewall headers (server runs behind a firewall). |
| `firewall_user` | If `firewall_auth=True` | Name of the firewall header carrying the username. |
| `firewall_email` | If `firewall_auth=True` | Name of the firewall header carrying the user's email. |

### Active Directory (`type = ActiveDirectory`)

| Option | Required | Description |
| --- | --- | --- |
| `ad_server` | Yes | Active Directory server. |
| `ad_domain` | Yes | Active Directory domain. |
| `ad_cert` | No | Path to the root CA certificate. |

### LDAP (`type = LDAP`)

| Option | Required | Description |
| --- | --- | --- |
| `ldap_server` | Yes | LDAP server URI. |
| `ldap_bind` | Yes | Bind string. May contain `{username}`, for example `uid={username},ou=Users,dc=eufus,dc=eu`. |
| `ldap_query_base` | Yes | Search base, for example `dc=eufus,dc=eu`. |
| `ldap_query_filter` | Yes | Filter to find the user. May contain `{username}`, for example `(uid={username})`. |
| `ldap_query_user` | No | Bind user for queries. If omitted, queries run as the authenticated user. |
| `ldap_query_password` | No | Password for `ldap_query_user`. Required if `ldap_query_user` is set. |
| `ldap_query_uid` | No | Name of the user parameter in the search result. Defaults to `uid`. |
| `ldap_query_mail` | No | Name of the email parameter in the search result. Defaults to `mail`. |

### Keycloak (`type = KeyCloak`)

Clients send their Keycloak access token in a `KeyCloak-Token` request header.

| Option | Required | Description |
| --- | --- | --- |
| `sever_url` | Yes | Keycloak server URL. The key is spelled `sever_url` in the current release. |
| `realm_name` | Yes | Keycloak realm name. |
| `client_id` | Yes | Keycloak client ID. |

```{note}
Keycloak support is experimental. Enable it only if you have verified it against
your Keycloak deployment.
```

See [Configure authentication](../how-to/operate-server/configure-authentication.md).

## `[cache]`

| Option | Required | Description |
| --- | --- | --- |
| `type` | No | `NullCache` (default), `SimpleCache`, or `FileSystemCache`. |
| `dir` | No | Directory for `FileSystemCache`. |
| `default_timeout` | No | Default cache timeout in seconds. |
| `threshold` | No | Maximum number of items before eviction (`SimpleCache`/`FileSystemCache`). |

More options are available; take any setting from the
[Flask-Caching documentation](https://flask-caching.readthedocs.io/en/latest/#built-in-cache-backends),
drop the `CACHE_` prefix and lowercase it, for example `CACHE_ARGS` becomes
`args`.

## `[development]`

| Option | Required | Description |
| --- | --- | --- |
| `disable_checksum` | No | `True`/`False`: skip integrity checks. For testing only. Defaults to `False`. |

## `[celery]`

Used by the optional
[background workers](../how-to/operate-server/run-celery-workers.md).

| Option | Required | Description |
| --- | --- | --- |
| `broker_url` | For workers | Message broker URL, for example `redis://redis:6379/0`. |
| `result_backend` | For workers | Result backend URL, for example `redis://redis:6379/0`. |
| `task_soft_time_limit` | No | Seconds before a running task is asked to stop. Ingestion tasks turn this into a `COPY_FAILED` status. Defaults to `3600`. |
| `task_time_limit` | No | Hard limit in seconds, after which the task is killed. Defaults to `3660`. |
| `stale_sweep_interval` | No | How often, in seconds, beat runs the stale-ingestion sweep. Defaults to `300`. |
| `stale_ingestion_timeout` | No | How long, in seconds, a simulation may sit in a non-terminal ingestion state before the sweep fails it. Should be larger than `task_time_limit`. Defaults to `7200`. |

## `[partition]`

| Option | Required | Description |
| --- | --- | --- |
| `data` | No | Directory used for partitioned data, for example `/data/simdb/partition`. |
| `http` | For `push` | Directory where resumable HTTP uploads are staged before ingestion, for example `/var/lib/simdb/http-staging`. Required for `simdb simulation push` against a v1.3 server. |

## `[role "NAME"]`

Defines a named role. Each role section needs a `users` option.

| Option | Required | Description |
| --- | --- | --- |
| `users` | Yes | Comma-separated list of usernames in this role. |

Currently only the `admin` role is used: it grants access to the
`simdb remote admin` subcommands.

```ini
[role "admin"]
users = admin,user1,user2
```

## Example: SQLite server

```ini
[flask]
flask_env = development
debug = True
testing = True
secret_key = CHANGE_ME_TO_A_LONG_RANDOM_STRING

[server]
upload_folder = /tmp/simdb/simulations
ssl_enabled = False
admin_password = admin

[database]
type = sqlite

[validation]
auto_validate = True
error_on_fail = True

[email]
server = smtp.example.org
port = 465
user = simdb@example.org
password = CHANGE_ME

[authentication]
type = None
```

## Example: PostgreSQL server

```ini
[server]
upload_folder = /var/lib/simdb/simulations
ssl_enabled = False
admin_password = CHANGE_ME

[flask]
secret_key = CHANGE_ME_TO_A_LONG_RANDOM_STRING

[database]
type = postgres
host = localhost
port = 5432
user = simdb
password = simdb
db_name = simdb

[authentication]
type = None
```

## Validation schema

Servers can require specific metadata through a `validation-schema.yaml` file in
the same configuration directory as `app.cfg`. It uses
[Cerberus](https://docs.python-cerberus.org/) rules:

```yaml
description:
  required: true
  type: string
```

Clients can inspect the active schema with `simdb remote SERVER schema`. See
[Validation](../explanation/validation.md).
