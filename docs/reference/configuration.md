# Client configuration

The SimDB command line client is configured through an INI-style file named
`simdb.cfg`. This page documents where that file lives, how settings are
resolved, and which options it understands. For the server's `app.cfg`, see
[Server configuration](server-configuration.md).

## Where the configuration lives

SimDB reads up to two `simdb.cfg` files, plus environment variables:

| Source | Typical location | Notes |
| --- | --- | --- |
| Site config | system config directory for `simdb` | Optional, shared by all users on the machine. |
| User config | per-user config directory for `simdb` | Created automatically on first run. |
| Environment | `SIMDB_*` variables | See [Environment variables](#environment-variables). |

To print the exact path of your user config file:

```bash
simdb config path
```

On Linux this is usually `~/.config/simdb/simdb.cfg`; on macOS it is
`~/Library/Application Support/simdb/simdb.cfg`.

```{important}
On Linux and macOS the user config file **must** have `0600` permissions (read
and write for the owner only). SimDB refuses to start if the permissions are
wrong, because the file can contain authentication tokens. The CLI sets these
permissions for you when it writes the file; if you edit it by hand, run
`chmod 600 "$(simdb config path)"` afterwards.
```

## How settings are resolved

Settings are applied in order, with later sources overriding earlier ones:

1. Environment variables (`SIMDB_*`).
2. The site config file.
3. The user config file.

Passing `-c/--config-file FILE` to `simdb` reads `FILE` instead of the site and
user files (environment variables still apply).

## Managing configuration from the CLI

Manage the file through the CLI rather than editing it by hand, so it always
stays valid:

```bash
simdb config list             # show all options
simdb config get user.email   # read one option
simdb config set user.email me@example.org
simdb config delete user.email
```

Option names use dotted notation. A name like `remote.iter.url` maps to the
`url` option of the `[remote "iter"]` section. Tokens are masked in
`simdb config list` output.

Remotes have dedicated commands; prefer those over `config set` for remote
options. See [Configure remotes](../how-to/configure-remotes.md).

## Options

### `[user]`

| Option | Description |
| --- | --- |
| `name` | Your username, used as the default when authenticating to remotes. |
| `email` | Your email address, used when registering as a watcher. |

### `[remote "NAME"]`

One section per configured remote server. Manage these with
`simdb remote config` (see [Configure remotes](../how-to/configure-remotes.md)).

| Option | Description |
| --- | --- |
| `url` | Base URL of the remote SimDB API. Required. |
| `default` | `True` on the remote used when no remote name is given. |
| `username` | Username to authenticate with for this remote. |
| `token` | Authentication token, set by `simdb remote token new`. Masked in listings. |
| `firewall` | Firewall login type in front of the server, for example `F5`. |

### `[db]`

| Option | Description |
| --- | --- |
| `file` | Path to the local SQLite catalogue. Defaults to `sim.db` in the user data directory (for example `~/.local/share/simdb/sim.db`). |

### `[partition]`

Maps logical partition names to absolute directories on this machine. Used by
`simdb simulation push_local` to rewrite file paths into partition-relative URIs
that the server can resolve (see
[Push and pull simulations](../how-to/push-pull.md#configure-partitions)).

| Option | Description |
| --- | --- |
| `NAME` | Directory that partition `NAME` is mounted at, for example `data = /home/user/my_simdb_data`. |

### `[development]`

| Option | Description |
| --- | --- |
| `disable_checksum` | `True` to skip checksum calculation. For testing only; never set this for real data. |

## Environment variables

Any configuration option can be set with an environment variable. Take the
dotted option name, replace dots with underscores, prefix with `SIMDB_`, and
uppercase it:

| Option | Environment variable |
| --- | --- |
| `remote.iter.url` | `SIMDB_REMOTE_ITER_URL` |
| `user.email` | `SIMDB_USER_EMAIL` |

SimDB also recognises these special variables:

| Variable | Effect |
| --- | --- |
| `SIMDB_CONFIG_FILE` | Path to a config file to load (same as `-c`). |
| `SIMDB_USER_CONFIG_PATH` | Override the location of the user config file. |
| `SIMDB_SITE_CONFIG_PATH` | Override the location of the site config file. |
| `REQUESTS_CA_BUNDLE` | Path to a CA certificate bundle for verifying HTTPS connections to remotes. See [Connect to ITER](../how-to/connect-to-iter.md). |
