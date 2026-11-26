# Configure remotes

A *remote* is a SimDB server the client can talk to. Remotes are stored in your
[client configuration](../reference/configuration.md) file. Manage them with the
`simdb remote config` commands rather than editing the file by hand, so it stays
valid.

ITER users: see [Connect to ITER](connect-to-iter.md) for the ITER-specific
URL, firewall, and certificate setup.

## List remotes

```bash
simdb remote config list
```

## Add a remote

```bash
simdb remote config new NAME URL
```

For example:

```bash
simdb remote config new myserver https://example.org/simdb/api
```

### Choosing a remote name

Use a single lowercase word of letters and digits, such as `iter` or `iterdev`.
Do not use spaces or dots: SimDB reads the name back from the config file and
from dotted option names like `remote.NAME.url`, so a name like `"simdb pp"` or
`simdb.pp` is not recognised by commands such as `simdb simulation pull`. `-`,
`_` and capitals work in commands but cannot be used in
[environment variable](../reference/configuration.md#environment-variables)
overrides such as `SIMDB_REMOTE_NAME_URL`. Also avoid naming a remote after a simulation alias you
use, since commands with an optional `[REMOTE]` read a matching first value as
the remote.

## Set a default

The default remote is used whenever you omit the remote name from a `remote` or
`simulation` command:

```bash
simdb remote config set-default myserver
simdb remote config get-default
```

## Set per-remote options

```bash
simdb remote config set-option myserver username my-user
simdb remote config set-option myserver firewall F5
```

Common options are `url`, `username`, `firewall`, and `default`; see the
[configuration reference](../reference/configuration.md#remote-name).

## Remove a remote

```bash
simdb remote config delete myserver
```

## Test a remote

```bash
simdb remote test            # default remote
simdb remote myserver test   # named remote
simdb remote myserver version
```

Next: set up [authentication](authenticate.md) so you do not have to enter
credentials on every command.
