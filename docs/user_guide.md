# Simdb Usage

Before running the simulation management tool you need to set up the environment.
This can be done with the following:

```bash
module load imas
imasdb <DB_NAME>
```

The simulation management tool has in-built help for all commands:

```bash
./simdb.sh --help

usage: simdb [-h] [--debug]
             {simulation,manifest,database,remote,provenance,summary} ...

optional arguments:
  -h, --help            show this help message and exit
  --debug, -d           run in debug mode

commands:
  {simulation,manifest,database,remote,provenance,summary}
    simulation          manage ingested simulations
    manifest            create/check manifest file
    database            manage local simulation database file
    remote              query remote system
    provenance          provenance tools
    summary             create and ingest IMAS summaries
```

Each subcommand is described in more detail in later sections.

Each subcommand has it's own help documentation, e.g.:

```bash
./simdb.sh simulation --help

usage: simdb simulation [-h]
                        {push,modify,list,info,delete,query,ingest,validate,new}
                        ...

optional arguments:
  -h, --help            show this help message and exit

action:
  {push,modify,list,info,delete,query,ingest,validate,new}
    push                push the simulation to the remote management system
    modify              modify the ingested simulation
    list                list ingested manifests
    info                print information on ingested manifest
    delete              delete an ingested manifest
    query               query the simulations
    ingest              ingest a manifest file
    validate            validate the ingested simulation
    new                 create a new blank simulation and return the UUID
```

## Manifest

Simulation manifest files describe the input, output and metadata for a simulation. The `manifest` subcommand is used to create and check the manifest files.

```bash
./simdb.sh manifest --help

usage: simdb manifest [-h] {check,create} manifest_file

positional arguments:
  {check,create}
  manifest_file   manifest file location

optional arguments:
  -h, --help      show this help message and exit
```

**Create**:

Creating a new template manifest file:
```bash
./simdb.sh manifest create temp.yaml
```

**Check**:

Checking a manifest for errors:
```bash
./simdb.sh manifest check locust.yaml
```

## Simulations

The `simulation` subcommand is used to ingest manifest files and manage ingested simulations. Ingested simulations
are stored in a local database which can be queried and validated, and when a simulation is ready to publish it can
be pushed to the remote simulation store.

```bash
./simdb.sh simulation --help

usage: simdb simulation [-h]
                        {push,modify,list,info,delete,query,ingest,validate,new}
                        ...

optional arguments:
  -h, --help            show this help message and exit

action:
  {push,modify,list,info,delete,query,ingest,validate,new}
    push                push the simulation to the remote management system
    modify              modify the ingested simulation
    list                list ingested manifests
    info                print information on ingested manifest
    delete              delete an ingested manifest
    query               query the simulations
    ingest              ingest a manifest file
    validate            validate the ingested simulation
    new                 create a new blank simulation and return the UUID
```

**Ingest**:

You store a simulation into the local database using:
```bash
./simdb.sh simulation ingest [-a|--alias ALIAS] manifest.yaml
```

The `alias` is optional but allows for easier referencing of the ingested simulation in other commands.

**List**:

The simulations stored in the local database can be seen using:
```bash
./simdb.sh simulation list [-v|--verbose]
```

The `verbose` argument is an optional switch which causes more information about each simulation to be printed.

**Info**:

You can view an ingested simulation using:
```bash
./simdb.sh simulation info <UUID|ALIAS>
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a
user given alias (either via the `ingest` or `modify` subcommands).

**Modify**:

If you want to modify an ingested simulation you can use:
```bash
./simdb.sh simulation modify [--alias ALIAS] <UUID|ALIAS>
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a
user given alias (either via the `ingest` or `modify` subcommands).

Currently the only thing you can modify on the simulation is the simulations alias but additional fields will be added
later such as the data quality flag, etc.

**Validate**:

To validate an ingested simulation use:
```bash
./simdb.sh simulation validate <UUID|ALIAS>
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a
user given alias (either via the `ingest` or `modify` subcommands).

**Query**:

You can query the simulations in the local database using:
```bash
./simdb.sh simulation query <KEY> --contains <VALUE>
./simdb.sh simulation query <KEY> --equals <VALUE>
```

This query returns all simulations where the value of `KEY` in the simulations metadata matches the given query condition.
E.g.

```bash
./simdb.sh simulation query publisher --equals ITER
```

## Provenance

The simulation provenance file is used to specify the machine and environment in which the simulation along with any
other provenance information required to re-run the simulation. This data is stored in the simulation database as
key-value pairs.

```bash
./simdb.sh provenance --help

usage: simdb provenance [-h] {create,ingest,print,query} ...

optional arguments:
  -h, --help            show this help message and exit

action:
  {create,ingest,print,query}
    create              create the provenance file from the current system
    ingest              ingest the provenance file
    print               print the provenance for a simulation
    query               query the simulations
```

**Create**:

To create a provenance file with values from the current system use:

```bash
./simdb.sh provenance create <FILE>
```

This runs some commands to dump the current environment and platform information so can be run as part of the simulation
scripts to generate the provenance file for the particular simulation run.

**Ingest**:

To ingest the file and store the provenance against an ingested simulation use:

```bash
./simdb.sh provenance ingest <UUID|ALIAS> <FILE>
```

This reads all the values in the provenance file and stores it with the specified simulation.

**Print**:

To print the provenance information for an ingested simulation use:

```bash
./simdb.sh provenance print <UUID|ALIAS>
```

**Query**:

To query the simulation providence use:
```bash
./simdb.sh provenance query <KEY> --contains <VALUE>
./simdb.sh provenance query <KEY> --equals <VALUE>
```

E.g.

```bash
./simdb.sh provenance query platform.architecture --contains 64
```

## Summary

The `summary` command is used to generate a summary file from a summary IDS. This summary file can then be ingested
and stored with a simulation, and ingested summaries can be listed and queried.

```bash
./simdb.sh summary --help

usage: simdb summary [-h] {create,ingest,query,list} ...

optional arguments:
  -h, --help            show this help message and exit

action:
  {create,ingest,query,list}
    create              create the summary file
    ingest              ingest the summary file
    query               query the simulations
    list                list the ingested summaries
```

**Create**:

Creating a summary yaml file using `create_db_summary` tool:

```bash
./simdb.sh summary create <FILE> <IDS_SHOT> <IDS_RUN>
```

The IMAS database used is the one set via the `imasdb` tool.

**Ingest**:

Ingest a summary file and store with an ingested simulation:
```bash
./simdb.sh summary ingest <UUID> <FILE>
```

**List**:

List summary information for a simulation:
```bash
./simdb.sh summary list <UUID>
```

**Query**:

Query summary data:
```bash
./simdb.sh summary query <KEY> --contains <VALUE>
./simdb.sh summary query <KEY> --equals <VALUE>
```

## Remote

Once a simulation is complete, all metadata and provenance data have been stored with it, and it is ready to publish
then the remote command is used to upload the simulation to the remote repository. The command can also be used to query
for simulation available in the remote repository.

```bash
./simdb.sh remote --help

usage: simdb remote [-h] [-v] {list,info,publish,delete,database} ...

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         print more verbose output

action:
  {list,info,publish,delete,database}
    list                list ingested manifests
    info                print information on ingested manifest
    publish             publish staged simulation
```

**Publish**:

To move a local simulation the remote staging are use:
```bash
./simdb.sh simulation publish <UUID|ALIAS>
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a
user given alias (either via the `simulation` `ingest` or `modify` subcommands).

**List**:

To see the simulations remotely staged use:
```bash
./simdb.sh remote list
```

**Info**:

To print information about a remotely staged simulation use:
```bash
./simdb.sh remote info <UUID>
```

The `UUID` is the generated unique identifer for the simulation, or you can reference the simulation using a
user given alias (either via the `simulation` `ingest` or `modify` subcommands).

## Database (admin tools)

***Note***: The following commands are for development only -- they will be removed as the functionality they provide are automated.

```bash
./simdb.sh database --help

usage: simdb database [-h] {clear,cv,reference} ...

optional arguments:
  -h, --help            show this help message and exit

action:
  {clear,cv,reference}
    clear               clear the database
    cv                  manage controlled vocabulary
    reference           manage reference scenarios
```

**Clear**:

You clear the local database using:
```bash
./simdb.sh database clear
```

**CV**:

You can see which controlled vocabularies are in the local database using:
```bash
./simdb.sh database cv list
```

You can display the words in a particular vocabulary using:
```bash
./simdb.sh database cv print <VOCAB>
```

To create a new controlled vocabularies use:
```bash
./simdb.sh database cv new <VOCAB> <WORD> <WORD> ...
```

To add a new word/s to an existing controlled vocabulary use:
```bash
./simdb.sh database cv update <VOCAB> <NEW_WORD> <NEW_WORD> ...
```

You can clear a vocabulary using:
```bash
./simdb.sh database cv clear <VOCAB>
```

You can delete a vocabulary using:
```bash
./simdb.sh database cv delete <VOCAB>
```

**Reference**:

The reference validation parameters are used when validating IDS data. When you set an IDS as the reference IDS for a particular device and scenario then each field in that IDS will be read and statistics about that field will be saved in the database. When you come to validate an IDS with that same device and scenario the fields in that IDS will be compared to these statistics read from the database.

To set an IDS reference IDS use:

```bash
./simdb.sh database reference load --shot=<SHOT> --run=<RUN> --device=<DEVICE> --scenario=<SCENARIO> --ids=<IDS>
```

You can use the command to use the same IMAS files for multiple IDSs:
```bash
./simdb.sh database reference load --shot=<SHOT> --run=<RUN> --device=<DEVICE> --scenario=<SCENARIO> --ids=<IDS1> --ids=<IDS2> --ids=<IDS3> ...
```
TODO: Validation parameters not being loaded

You can list the reference IDSs stored using:
```bash
./simdb.sh database reference list
```

You can print the stored reference statistics for a device and scenario using:
```bash
./simdb.sh database reference print --device=<DEVICE> --scenario=<SCENARIO>
```

You can delete all the reference statistics for a device and scenario using:
```bash
./simdb.sh database reference delete --device=<DEVICE> --scenario=<SCENARIO>
```

