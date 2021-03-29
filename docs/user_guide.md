# simdb usage

Before running the simulation management tool you need to set up the environment. This can be done with the following:

```bash
module load imas
```

The simulation management tool has in-built help for all commands:

```text
simdb --help
Usage: simdb [OPTIONS] COMMAND [ARGS]...

Options:
  --version      Show the version and exit.
  -d, --debug    Run in debug mode.
  -v, --verbose  Run with verbose output.
  --help         Show this message and exit.

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

Each subcommand is described in more detail in later sections.

Each subcommand has it's own help documentation, e.g.:

```text
simdb simulation --help
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

## Manifest

Simulation manifest files describe the input, output and metadata for a simulation. The `manifest` subcommand is used to create and check the manifest files.

```text
Usage: simdb manifest [OPTIONS] COMMAND [ARGS]...

  Create/check manifest file.

Options:
  --help  Show this message and exit.

Commands:
  check   Check manifest FILE_NAME.
  create  Create a new MANIFEST_FILE.

```

**Create**:

Creating a new template manifest file:
```text
Usage: simdb manifest create [OPTIONS] MANIFEST_FILE

  Create a new MANIFEST_FILE.

Options:
  --help  Show this message and exit.
```

**Check**:

Checking a manifest for errors:
```text
Usage: simdb manifest check [OPTIONS] FILE_NAME

  Check manifest FILE_NAME.

Options:
  --help  Show this message and exit.
```

## Simulations

The `simulation` subcommand is used to ingest manifest files and manage ingested simulations. Ingested simulations
are stored in a local database which can be queried and validated, and when a simulation is ready to publish it can
be pushed to the remote simulation store.

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

**Ingest**:

You store a simulation into the local database using:
```text
Usage: simdb simulation ingest [OPTIONS] MANIFEST_FILE

  Ingest a MANIFEST_FILE.

Options:
  -a, --alias TEXT  Alias to give to simulation (overwrites any set in
                    manifest).

  --help            Show this message and exit.
```

The `alias` is optional but allows for easier referencing of the ingested simulation in other commands.

**List**:

The simulations stored in the local database can be seen using:
```text
Usage: simdb simulation list [OPTIONS]

  List ingested simulations.

Options:
  -m, --meta-data TEXT  Additional meta-data field to print.
  --help                Show this message and exit.
```

**Info**:

You can view an ingested simulation using:
```text
Usage: simdb simulation info [OPTIONS] SIM_ID

  Print information on the simulation with given SIM_ID (UUID or alias).

Options:
  --help  Show this message and exit.
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a user given alias (either via the `ingest` or `modify` subcommands).

**Modify**:

If you want to modify an ingested simulation you can use:
```text
Usage: simdb simulation modify [OPTIONS] SIM_ID

  Modify the ingested simulation.

Options:
  -a, --alias TEXT  New alias.
  --help            Show this message and exit.
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a user given alias (either via the `ingest` or `modify` subcommands).

Currently the only thing you can modify on the simulation is the simulations alias but additional fields will be added
later such as the data quality flag, etc.

**Validate**:

To validate an ingested simulation use:
```text
Usage: simdb simulation validate [OPTIONS] [REMOTE] SIM_ID

  Validate the ingested simulation with given SIM_ID (UUID or alias) using
  validation schema from REMOTE.

Options:
  --help  Show this message and exit.
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a
user given alias (either via the `ingest` or `modify` subcommands).

**Query**:

You can query the simulations in the local database using:
```text
Usage: simdb simulation query [OPTIONS] [CONSTRAINT]...

  Query the simulations.

Options:
  --help  Show this message and exit.
```

This query returns all simulations where the value of `KEY` in the simulations metadata matches the given query condition.
E.g.

```text
simdb simulation query publisher=ITER
```

## Provenance

This runs some commands to dump the current environment and platform information so can be run as part of the simulation scripts to generate the provenance file for the particular simulation run.

```text
Usage: simdb provenance [OPTIONS] PROVENANCE_FILE

  Create the PROVENANCE_FILE from the current system.

Options:
  --help  Show this message and exit.
```

## Remote

Once a simulation is complete, all metadata and provenance data have been stored with it, and it is ready to publish then the remote command is used to upload the simulation to the remote repository. The command can also be used to query for simulation available in the remote repository.

```text
Usage: simdb remote [OPTIONS] [NAME] COMMAND [ARGS]...

  Interact with the remote SimDB service.

Options:
  --help  Show this message and exit.

Commands:
  database  Reset remote database.
  delete    Delete specified remote simulations.
  info      Print information about simulation with given SIM_ID (UUID or...
  list      List simulation available on remote.
  publish   Mark remote simulation as published.
  query     Perform a metadata query to find matching simulation from...
  watcher   Manage simulaiton watchers on REMOTE SimDB server.
```

**Publish**:

To move a local simulation the remote staging are use:
```text
Usage: simdb remote publish [OPTIONS] SIM_ID

  Mark remote simulation as published.

Options:
  --help  Show this message and exit.
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a
user given alias (either via the `simulation` `ingest` or `modify` subcommands).

**List**:

To see the simulations remotely staged use:
```text
Usage: simdb remote list [OPTIONS]

  List simulation available on remote.

Options:
  -m, --meta-data TEXT  Additional meta-data field to print.
  --help                Show this message and exit.
```

**Info**:

To print information about a remotely staged simulation use:
```text
Usage: simdb remote info [OPTIONS] SIM_ID

  Print information about simulation with given SIM_ID (UUID or alias) from
  remote.

Options:
  --help  Show this message and exit.
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a
user given alias (either via the `simulation` `ingest` or `modify` subcommands).

## Database (admin tools)

***Note***: The following commands are for development only -- they will be removed as the functionality they provide are automated.

```text
Usage: simdb database [OPTIONS] COMMAND [ARGS]...

  Manage local simulation database.

Options:
  --help  Show this message and exit.

Commands:
  clear  Clear the database.
```

**Clear**:

You clear the local database using:
```text
Usage: simdb database clear [OPTIONS]

  Clear the database.

Options:
  --help  Show this message and exit.
```
