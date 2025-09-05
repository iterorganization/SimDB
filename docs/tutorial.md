# SimDB CLI Tutorial

This tuturial covers the basics of how to use the SimDB CLI to catalogue a simulation and interacting with remote
simulation databases.

## Checking the CLI

The first thing to do is check that the SimDB CLI is available. You can do this by running:

```bash
simdb --version
```

This should return something similar to:

```
simdb, version 0.4.0
```

This indicates the CLI is available and shows what version has been installed.

## CLI help

The SimDB CLI has internal help documentation that you can run by providing the `--help` argument. This can be done at
different levels of commands and will show the help documentation for that level of command. For example `simdb --help`
shows the top level help, whereas `simdb remote --help` shows the help for the `remote` command.

Running:

```bash
simdb --help
```

Should show the following:

```
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
  sim         Alias for None.
  simulation  Manage ingested simulations.
```

## Creating a simulation manifest

The first step in ingesting a simulation is to create the manifest file. This file is a small YAML file that specifies
some key elements about the simulation as well as allowing additional meta-data to be attached.

Create a file called `manifest.yaml` which contains the following.

```yaml
manifest_version: 2
alias: simulation-alias
inputs:
- uri: file:///my/input/file
- uri: imas:hdf5?path=/path/to/imas/data
outputs:
- uri: imas:hdf5?path=/path/to/more/data
metadata:
- machine: name of machine i.e. ITER.
- code:
    name: code name i.e. ASTRA, JETTO, DINA, CORSICA, MITES, SOLPS, JINTRAC etc.
- simulation:
    description: |-
    Sample plasma physics simulation for ITER tokamak modeling
    reference_name: ITER simulation
- ids_properties:
    creation_date: 'YYYY-MM-DD HH:mm:ss'
```

The `version` field is mandatory and specifies which manifest version you are using. This should be set 1 for the latest
version.

The `alias` field is optional and provides a way of providing an alias which can be used to find the simulation later.
This alias can also be provided on the command line when the manifest file is read, see later.

The `metadata` field is a list of `values` or `path` elements. The `values` elements are dictionaries of metadata to be
stored with the simulation. The `path` elements are paths to YAML files containing metadata in case the metadata is
better written in a separate file.

The `inputs` and `outputs` are lists of `uri`s which specify the location of the input and output data for the
simulation. These data will be checksummed when the simulation is ingested and copied to the remote server if you decide
to push the simulation, see later.

## Ingesting the manifest

Now that you have a manifest file you can ingest it using the following command:

```bash
simdb simulation ingest manifest.yaml
```

This will ingest the simulation into your local simulation database. You can see what has been ingested using:

```bash
simdb simulation list
```

And the simulation you have just ingested with:

```bash
simdb simulation info test
```

## Pushing the simulation to remote server

The SimDB client is able to communication with multiple remote servers. You can see which remote servers are available
on your local client using:

```bash
simdb remote --list
```

First, you will need to add the remote server and set it as default:

```bash
simdb remote --new test https://io-ls-simdb01.iter.org:6000
simdb remote --set-default test
```

You can now list the simulations available on the remote server:

```bash
simdb remote list
```

Whenever you run a remote command you will notice that you have to authenticate against the remote server. This can be
avoided by creating an authentication token using:

```bash
simdb remote token new
```

This will request a token from the remote server which is stored in a locally to allow you to authenticate against the
server without having to provide credentials on each command.