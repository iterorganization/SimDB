# SimDB CLI commands

```text
Usage: simdb [OPTIONS] COMMAND [ARGS]...

Options:
  --version                   Show the version and exit.
  -d, --debug                 Run in debug mode.
  -v, --verbose               Run with verbose output.
  -c, --config-file FILENAME  Config file to load.
  --help                      Show this message and exit.

Commands:
  alias       Query remote and local aliases.
  config      Query/update application configuration.
  database    Manage local simulation database.
  dump-help
  manifest    Create/check manifest file.
  provenance  Create the PROVENANCE_FILE from the current system.
  remote      Interact with the remote SimDB service.
  simulation  Manage ingested simulations.
```

## Manifest

```text
Usage: simdb manifest [OPTIONS] COMMAND [ARGS]...

  Create/check manifest file.

Options:
  --help  Show this message and exit.

Commands:
  check   Check manifest FILE_NAME.
  create  Create a new MANIFEST_FILE.
```

```text
Usage: simdb manifest check [OPTIONS] FILE_NAME

  Check manifest FILE_NAME.

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb manifest create [OPTIONS] MANIFEST_FILE

  Create a new MANIFEST_FILE.

Options:
  --help  Show this message and exit.
```

## Alias 

```text
Usage: simdb alias [OPTIONS] COMMAND [ARGS]...

  Query remote and local aliases.

Options:
  --help  Show this message and exit.

Commands:
  list    List aliases from the local database and the REMOTE (if...
  search  Search the REMOTE for all aliases that contain the given VALUE.
```

```text
Usage: simdb alias search [OPTIONS] [REMOTE] VALUE

  Search the REMOTE for all aliases that contain the given VALUE.

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --help           Show this message and exit.
```

```text
Usage: simdb alias list [OPTIONS] [REMOTE]

  List aliases from the local database and the REMOTE (if specified).

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --help           Show this message and exit.
```

## Simulation

```text
Usage: simdb simulation [OPTIONS] COMMAND [ARGS]...

  Manage ingested simulations.

Options:
  --help  Show this message and exit.

Commands:
  alias     Generate a unique alias with the given PREFIX.
  delete    Delete the ingested simulation with given SIM_ID (UUID or...
  info      Print information on the simulation with given SIM_ID (UUID or...
  ingest    Ingest a MANIFEST_FILE.
  list      List ingested simulations.
  modify    Modify the ingested simulation.
  new       Create an empty simulation in the database which can be updated...
  push      Push the simulation with the given SIM_ID (UUID or alias) to
            the...

  query     Query the simulations.
  validate  Validate the ingested simulation with given SIM_ID (UUID or...
```

```text
Usage: simdb simulation new [OPTIONS]

  Create an empty simulation in the database which can be updated later.

Options:
  -a, --alias TEXT  Alias of to assign to the simulation.
  -u, --uuid-only   Return a new UUID but do not insert the new simulation
                    into the database.

  --help            Show this message and exit.
```

```text
Usage: simdb simulation alias [OPTIONS]

  Generate a unique alias with the given PREFIX.

Options:
  -p, --prefix TEXT  Prefix to use for the alias.  [default: sim]
  --help             Show this message and exit.
```

```text
Usage: simdb simulation list [OPTIONS]

  List ingested simulations.

Options:
  -m, --meta-data TEXT  Additional meta-data field to print.
  --help                Show this message and exit.
```

```text
Usage: simdb simulation modify [OPTIONS] SIM_ID

  Modify the ingested simulation.

Options:
  -a, --alias TEXT  New alias.
  --help            Show this message and exit.
```

```text
Usage: simdb simulation delete [OPTIONS] SIM_ID

  Delete the ingested simulation with given SIM_ID (UUID or alias).

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb simulation info [OPTIONS] SIM_ID

  Print information on the simulation with given SIM_ID (UUID or alias).

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb simulation ingest [OPTIONS] MANIFEST_FILE

  Ingest a MANIFEST_FILE.

Options:
  -a, --alias TEXT  Alias to give to simulation (overwrites any set in
                    manifest).

  --help            Show this message and exit.
```

```text
Usage: simdb simulation push [OPTIONS] [REMOTE] SIM_ID

  Push the simulation with the given SIM_ID (UUID or alias) to the REMOTE.

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --replaces TEXT  SIM_ID of simulation to deprecate and replace.
  --help           Show this message and exit.
```

```text
Usage: simdb sim pull [OPTIONS] [REMOTE] SIM_ID DIRECTORY

  Pull the simulation with the given SIM_ID (UUID or alias) from the REMOTE.

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --help           Show this message and exit.
```

```text
Usage: simdb simulation query [OPTIONS] [CONSTRAINT]...

  Query the simulations.

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb simulation validate [OPTIONS] [REMOTE] SIM_ID

  Validate the ingested simulation with given SIM_ID (UUID or alias) using
  validation schema from REMOTE.

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --help           Show this message and exit.
```

## Config

```text
Usage: simdb config [OPTIONS] COMMAND [ARGS]...

  Query/update application configuration.

Options:
  --help  Show this message and exit.

Commands:
  delete  Delete the OPTION.
  get     Get the OPTION.
  list    List all configurations OPTIONS set.
  set     Set the OPTION to the given VALUE.
```

```text
Usage: simdb config get [OPTIONS] OPTION

  Get the OPTION.

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb config set [OPTIONS] OPTION VALUE

  Set the OPTION to the given VALUE.

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb config delete [OPTIONS] OPTION

  Delete the OPTION.

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb config list [OPTIONS]

  List all configurations OPTIONS set.

Options:
  --help  Show this message and exit.
```

## Database

```text
Usage: simdb database [OPTIONS] COMMAND [ARGS]...

  Manage local simulation database.

Options:
  --help  Show this message and exit.

Commands:
  clear  Clear the database.
```

```text
Usage: simdb database clear [OPTIONS]

  Clear the database.

Options:
  --help  Show this message and exit.
```

## Remote

```text
Usage: simdb remote [OPTIONS] [NAME] COMMAND [ARGS]...

  Interact with the remote SimDB service.

  If NAME is provided this determines which remote server to communicate
  with, otherwise the server in the config file with default=True is used.

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --help           Show this message and exit.

Commands:
  info     Print information about simulation with given SIM_ID (UUID or...
  list     List simulations available on remote.
  query    Perform a metadata query to find matching simulation from remote.
  token    Manage user authentication tokens.
  update   Mark remote simulation as published.
  watcher  Manage simulation watchers on REMOTE SimDB server.
```

```text
Usage: simdb remote [NAME] watcher [OPTIONS] COMMAND [ARGS]...

  Manage simulation watchers on REMOTE SimDB server.

Options:
  --help  Show this message and exit.

Commands:
  add     Register a user as a watcher for a simulation with given SIM_ID...
  list    List watchers for simulation with given SIM_ID (UUID or alias).
  remove  Remove a user from list of watchers on a simulation with given...
```

```text
Usage: simdb remote watcher list [OPTIONS] SIM_ID

  List watchers for simulation with given SIM_ID (UUID or alias).

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb remote watcher remove [OPTIONS] SIM_ID

  Remove a user from list of watchers on a simulation with given SIM_ID
  (UUID or alias).

Options:
  -u, --user TEXT  Name of the user to remove as a watcher.
  --help           Show this message and exit.
```

```text
Usage: simdb remote watcher add [OPTIONS] SIM_ID

  Register a user as a watcher for a simulation with given SIM_ID (UUID or
  alias).

Options:
  -u, --user TEXT                 Name of the user to add as a watcher.
  -e, --email TEXT                Email of the user to add as a watcher.
  -n, --notification [VALIDATION|REVISION|OBSOLESCENCE|ALL]
                                  [default: ALL]
  --help                          Show this message and exit.
```

```text
Usage: simdb remote [NAME] list [OPTIONS]

  List simulations available on remote.

Options:
  -m, --meta-data TEXT  Additional meta-data field to print.
  --help                Show this message and exit.
```

```text
Usage: simdb remote [NAME] info [OPTIONS] SIM_ID

  Print information about simulation with given SIM_ID (UUID or alias) from
  remote.

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb remote [NAME] query [OPTIONS] [CONSTRAINTS]...

  Perform a metadata query to find matching simulation from remote.

Options:
  -m, --meta-data TEXT  Additional meta-data field to print.
  --help                Show this message and exit.
```

```text
Usage: simdb remote [NAME] update [OPTIONS] SIM_ID [validate|accept|deprecate]

  Mark remote simulation as published.

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb remote [NAME] token [OPTIONS] COMMAND [ARGS]...

  Manage user authentication tokens.

Options:
  --help  Show this message and exit.

Commands:
  delete
  new
```

```text
Usage: simdb remote token new [OPTIONS]

Options:
  --help  Show this message and exit.
```

```text
Usage: simdb remote token delete [OPTIONS]

Options:
  --help  Show this message and exit.
```

## Provenance

```text
Usage: simdb provenance [OPTIONS] PROVENANCE_FILE

  Create the PROVENANCE_FILE from the current system.

Options:
  --help  Show this message and exit.
```
