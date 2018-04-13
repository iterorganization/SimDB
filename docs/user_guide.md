# Simdb Usage

Setting up envioronment:
```bash
module load imas
imasdb locust
```

The simulation management tool has in-built help for all commands:
```bash
./simdb.sh --help
```

Each subcommand has it's own help documentation:
```bash
./simdb.sh simulation --help
```

The subcommands are:
* **simulation**:          manage ingested simulations
* **manifest**:            create/check manifest file
* **database**:            manage local simulation database file
* **remote**:              query remote system
* **provenance**:          provenance tools
* **summary**:             create and ingest IMAS summaries

## Manifest

Simulation manifest files describe the input, output and metadata for a simulation. The `manifest` subcommand is used to create and check the manifest files.

Creating a new template manifest file:
```bash
./simdb.sh manifest create temp.yaml
```

Checking a manifest for errors:
```bash
./simdb.sh manifest check locust.yaml
```

## Simulations

You store a simulation into the local database using:
```bash
./simdb.sh simulation ingest --alias ALIAS manifest.yaml
```

The simulations stored in the local database can be seen using:
```bash
./simdb.sh simulation list
```

You can view an ingested simulation using:
```bash
./simdb.sh simulation info <UUID|ALIAS>
```

If you want to modify an ingested simulation you can use:
```bash
./simdb.sh simulation modify --alias ALIAS <UUID>
```

To validate an ingested simulation use:
```bash
./simdb.sh simulation validate <UUID|ALIAS>
```
TODO: Failing to validate IDS objects

You can query the simulations in the local database using:
```bash
./simdb.sh simulation query <KEY> --contains <VALUE>
./simdb.sh simulation query <KEY> --equals <VALUE>
```

## Remote

To move a local simulation the remote staging are use:
```bash
./simdb.sh simulation push <UUID|ALIAS>
```
TODO: Add progress meter

To see the simulations remotely staged use:
```bash
./simdb.sh remote list
```

To print information about a remotely staged simulation use:
```bash
./simdb.sh remote info <UUID>
```

TODO: Add remote modify

## Provenance

To create a provenance file with values from the current system use:
```bash
./simdb.sh provenance create <FILE>
```

To ingest the file and store the provenance against an ingested simulation use:
```bash
./simdb.sh provenance ingest <UUID|ALIAS> <FILE>
```

To print the provenance information for an ingested simulation use:
```bash
./simdb.sh provenance print <UUID|ALIAS>
```

To query the simulation providence use:
```bash
./simdb.sh provenance query <KEY> --contains <VALUE>
./simdb.sh provenance query <KEY> --equals <VALUE>
```

## Summary

Creating a summary yaml file using `create_db_summary` tool:
```bash
./simdb.sh summary create summary.yaml
```

Ingest a summary file and store with an ingested simulation:
```bash
./simdb.sh summary ingest <UUID> summary.yaml
```

List summary information for a simulation:
```bash
./simdb.sh summary list <UUID>
```

Query summary data:
```bash
./simdb.sh summary query <KEY> --contains <VALUE>
./simdb.sh summary query <KEY> --equals <VALUE>
```

## Database (admin tools)

You clear the local database using:
```bash
./simdb.sh database clear
```

### Controlled vocabularies

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

### Reference validation parameters

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

