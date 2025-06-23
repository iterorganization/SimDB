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
  manifest    Create/check manifest file.
  provenance  Create the PROVENANCE_FILE from the current system.
  remote      Interact with the remote SimDB service.
  sim         Alias for simulation.
  simulation  Manage ingested simulations.
```
    
## Alias


```text
Usage: simdb alias [OPTIONS] [REMOTE] COMMAND [ARGS]...

  Query remote and local aliases.

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --help           Show this message and exit.

Commands:
  list         List aliases from the local database and the REMOTE (if...
  make-unique  Make the given alias unique, checking locally stored...
  search       Search the REMOTE for all aliases that contain the given...
```
    

```text
Usage: simdb alias [REMOTE] list [OPTIONS]

  List aliases from the local database and the REMOTE (if specified).

Options:
  --local  Only list the local aliases.
  --help   Show this message and exit.
```
    

```text
Usage: simdb alias [REMOTE] make-unique [OPTIONS] ALIAS

  Make the given alias unique, checking locally stored simulations and the
  remote.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb alias [REMOTE] search [OPTIONS] ALIAS

  Search the REMOTE for all aliases that contain the given VALUE.

Options:
  --help  Show this message and exit.
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
  path    Print the location of the user configuration file.
  set     Set the OPTION to the given VALUE.
```
    

```text
Usage: simdb config delete [OPTIONS] OPTION

  Delete the OPTION.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb config get [OPTIONS] OPTION

  Get the OPTION.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb config list [OPTIONS]

  List all configurations OPTIONS set.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb config path [OPTIONS]

  Print the location of the user configuration file.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb config set [OPTIONS] OPTION VALUE

  Set the OPTION to the given VALUE.

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
    
## Provenance


```text
Usage: simdb provenance [OPTIONS] PROVENANCE_FILE

  Create the PROVENANCE_FILE from the current system.

Options:
  --help  Show this message and exit.
```
    
## Remote


```text
Usage: simdb remote [OPTIONS] [NAME] COMMAND [ARGS]...

  Interact with the remote SimDB service.

  If NAME is provided this determines which remote server to communicate with,
  otherwise the server in the config file with default=True is used.

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --help           Show this message and exit.

Commands:
  admin      Run admin commands on REMOTE SimDB server (requires admin...
  config     Configure the available remotes.
  directory  Print the storage directory of the remote.
  info       Print information about simulation with given SIM_ID (UUID...
  list       List simulations available on remote.
  query      Perform a metadata query to find matching remote simulations.
  schema     Show validation schemas for the given remote.
  test       Test that the remote is valid.
  token      Manage user authentication tokens.
  trace      Print provenance trace of simulation with given SIM_ID (UUID...
  version    Show the SimDB version of the remote.
  watcher    Manage simulation watchers on REMOTE SimDB server.
```
    

```text
Usage: simdb remote [NAME] admin [OPTIONS] COMMAND [ARGS]...

  Run admin commands on REMOTE SimDB server (requires admin privileges).

  Requires user to have admin privileges on remote.

Options:
  --help  Show this message and exit.

Commands:
  del-meta    Remove a metadata value for the given simulation.
  delete      Delete a simulation.
  set-meta    Add or update a metadata value for the given simulation.
  set-status  Update the status metadata value for the given simulation.
```
    

```text
Usage: simdb remote [NAME] admin del-meta [OPTIONS] SIM_ID KEY

  Remove a metadata value for the given simulation.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] admin delete [OPTIONS] SIM_ID

  Delete a simulation.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] admin set-meta [OPTIONS] SIM_ID KEY VALUE

  Add or update a metadata value for the given simulation.

Options:
  -t, --type [string|UUID|int|float]
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] admin set-status [OPTIONS] SIM_ID {NOT_VALIDATED|AC
                                            CEPTED|FAILED|PASSED|DEPRECATED|DE
                                            LETED}

  Update the status metadata value for the given simulation.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] config [OPTIONS] COMMAND [ARGS]...

  Configure the available remotes.

Options:
  --help  Show this message and exit.

Commands:
  default      Print the default remote.
  delete       Delete a remote.
  get-default  Get the name of the default remote.
  list         List available remotes.
  new          Add a new remote.
  set-default  Set a remote as default.
  set-option   Set a configuration option for a given remote.
```
    

```text
Usage: simdb remote [NAME] config default [OPTIONS]

  Print the default remote.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] config delete [OPTIONS] NAME

  Delete a remote.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] config get-default [OPTIONS]

  Get the name of the default remote.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] config list [OPTIONS]

  List available remotes.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] config new [OPTIONS] NAME URL

  Add a new remote.

Options:
  --firewall [F5]  Specify the remote is behind a login firewall and what type
                   it is.
  --username TEXT  Username to use for remote.
  --default        Set the new remote as the default.
  --help           Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] config set-default [OPTIONS] NAME

  Set a remote as default.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] config set-option [OPTIONS] NAME OPTION VALUE

  Set a configuration option for a given remote.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] directory [OPTIONS]

  Print the storage directory of the remote.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] info [OPTIONS] SIM_ID

  Print information about simulation with given SIM_ID (UUID or alias) from
  remote.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] list [OPTIONS]

  List simulations available on remote.

Options:
  -m, --meta-data NAME  Additional meta-data field to print.
  -l, --limit INTEGER   Limit number of returned entries (use 0 for no limit).
                        [default: 100]
  --help                Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] query [OPTIONS] [CONSTRAINTS]...

  Perform a metadata query to find matching remote simulations.

  Each constraint must be in the form:
      NAME=[mod]VALUE

  Where `[mod]` is an optional query modifier. Available query modifiers are:
      eq:  - This checks for equality (this is the same behaviour as not providing any modifier).
      in:  - This searches inside the value instead of looking for exact matches.
      gt:  - This checks for values greater than the given quantity.
      agt: - This checks for any array elements are greater than the given quantity.
      ge:  - This checks for values greater than or equal to the given quantity.
      age: - This checks for any array elements are greater than or equal to the given quantity.
      lt:  - This checks for values less than the given quantity.
      alt:  - This checks for any array elements are less than the given quantity.
      le:  - This checks for values less than or equal to the given quantity.
      ale:  - This checks for any array elements are less than or equal to the given quantity.

  Modifier examples:
      alias=eq:foo                                                performs exact match
      summary.code.name=in:foo                                    matches all names containing foo
      summary.heating_current_drive.power_additional.value=agt:0  matches all simulations where any array element of summary.heating_current_drive.power_additional.value is greater than 0

  Any string comparisons are done in a case-insensitive manner. If multiple constraints are provided then simulations
  are returned that match all given constraints.

  Examples:
      sim remote query workflow.name=in:test       finds all simulations where workflow.name contains test
                                                       (case-insensitive)
      sim remote query pulse=gt:1000 run=0         finds all simulations where pulse is > 1000 and run = 0

Options:
  -m, --meta-data TEXT  Additional meta-data field to print.
  -l, --limit INTEGER   Limit number of returned entries (use 0 for no limit).
                        [default: 100]
  --help                Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] schema [OPTIONS]

  Show validation schemas for the given remote.

Options:
  -d, --depth INTEGER  Limit the depth of elements of the schema printed to
                       the console.  [default: 2]
  --help               Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] test [OPTIONS]

  Test that the remote is valid.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] token [OPTIONS] COMMAND [ARGS]...

  Manage user authentication tokens.

Options:
  --help  Show this message and exit.

Commands:
  delete  Delete the existing token for the given remote.
  new     Create a new token for the given remote.
```
    

```text
Usage: simdb remote [NAME] token delete [OPTIONS]

  Delete the existing token for the given remote.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] token new [OPTIONS]

  Create a new token for the given remote.

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] trace [OPTIONS] SIM_ID

  Print provenance trace of simulation with given SIM_ID (UUID or alias) from
  remote.

  This shows a history of simulations that this simulation has replaced or
  been replaced by and what those simulations replaced or where replaced by
  and so on.

  If the outputs of this simulation are used as inputs of other simulations or
  if the inputs are generated by other simulations then these dependencies are
  also reported.

Options:
  --help  Show this message and exit.
```
<!--     

```text
Usage: simdb remote [NAME] update [OPTIONS] SIM_ID {validate|accept|deprecate}

  Mark remote simulation as published.

Options:
  --help  Show this message and exit.
``` -->
    

```text
Usage: simdb remote [NAME] version [OPTIONS]

  Show the SimDB version of the remote.

Options:
  --help  Show this message and exit.
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
Usage: simdb remote [NAME] watcher add [OPTIONS] SIM_ID

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
Usage: simdb remote [NAME] watcher list [OPTIONS] SIM_ID

  List watchers for simulation with given SIM_ID (UUID or alias).

Options:
  --help  Show this message and exit.
```
    

```text
Usage: simdb remote [NAME] watcher remove [OPTIONS] SIM_ID

  Remove a user from list of watchers on a simulation with given SIM_ID (UUID
  or alias).

Options:
  -u, --user TEXT  Name of the user to remove as a watcher.
  --help           Show this message and exit.
```
    
## Simulation


```text
Usage: simdb simulation [OPTIONS] COMMAND [ARGS]...

  Manage ingested simulations.

Options:
  --help  Show this message and exit.

Commands:
  delete    Delete the ingested simulation with given SIM_ID (UUID or...
  info      Print information on the simulation with given SIM_ID (UUID...
  ingest    Ingest a MANIFEST_FILE.
  list      List ingested simulations.
  modify    Modify the ingested simulation.
  pull      Pull the simulation with the given SIM_ID (UUID or alias)...
  push      Push the simulation with the given SIM_ID (UUID or alias) to...
  query     Perform a metadata query to find matching local simulations.
  validate  Validate the ingested simulation with given SIM_ID (UUID or...
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
Usage: simdb simulation list [OPTIONS]

  List ingested simulations.

Options:
  -m, --meta-data TEXT  Additional meta-data field to print.
  -l, --limit INTEGER   Limit number of returned entries (use 0 for no limit).
                        [default: 100]
  --help                Show this message and exit.
```
    

```text
Usage: simdb simulation modify [OPTIONS] SIM_ID

  Modify the ingested simulation.

Options:
  -a, --alias ALIAS      New alias.
  --set-meta NAME=VALUE  Add new meta or update existing.
  --del-meta NAME        Delete metadata entry.
  --help                 Show this message and exit.
```
    

```text
Usage: simdb simulation pull [OPTIONS] [REMOTE] SIM_ID DIRECTORY

  Pull the simulation with the given SIM_ID (UUID or alias) from the REMOTE.

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --help           Show this message and exit.
```
    

```text
Usage: simdb simulation push [OPTIONS] [REMOTE] SIM_ID

  Push the simulation with the given SIM_ID (UUID or alias) to the REMOTE.

Options:
  --username TEXT  Username used to authenticate with the remote.
  --password TEXT  Password used to authenticate with the remote.
  --replaces TEXT  SIM_ID of simulation to deprecate and replace.
  --add-watcher    Add the current user as a watcher of the simulation.
  --help           Show this message and exit.
```
    

```text
Usage: simdb simulation query [OPTIONS] [CONSTRAINTS]...

  Perform a metadata query to find matching local simulations.

  Each constraint must be in the form:
      NAME=[mod]VALUE

  Where `[mod]` is an optional query modifier. Available query modifiers are:
      eq: - This checks for equality (this is the same behaviour as not providing any modifier).
      ne: - This checks for value that do not equal.
      in: - This searches inside the value instead of looking for exact matches.
      ni: - This searches inside the value for elements that do not match.
      gt: - This checks for values greater than the given quantity.
      ge: - This checks for values greater than or equal to the given quantity.
      lt: - This checks for values less than the given quantity.
      le: - This checks for values less than or equal to the given quantity.

  For the following modifiers, VALUE should not be provided.     exist: - This
  returns simulations where metadata with NAME exists, regardless of the
  value.

  Modifier examples:
      responsible_name=foo        performs exact match
      responsible_name=in:foo     matches all names containing foo
      pulse=gt:1000               matches all pulses > 1000
      sequence=exist:             matches all simulations that have "sequence" metadata values

  Any string comparisons are done in a case-insensitive manner. If multiple constraints are provided then simulations
  are returned that match all given constraints.

  Examples:
      sim simulation query workflow.name=in:test       finds all simulations where workflow.name contains test
                                                       (case-insensitive)
      sim simulation query pulse=gt:1000 run=0         finds all simulations where pulse is > 1000 and run = 0

Options:
  -m, --meta-data TEXT  Additional meta-data field to print.
  --help                Show this message and exit.
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
    
