# SimDB user guide

This page covers the core functionality of the SimDB command line, and some common use cases.

Further details on the command line interface can be found [here](cli.md).

## Basic usage

SimDB is a command line interface (CLI) that can be used to store metadata about simulation runs and their associated data. These simulations are stored locally for the user until they are pushed to a remote SimDB server where they can then be queried by any user.

To run the SimDB CLI you can use the following:

```bash
simdb --version
```

This will print out the version of SimDB available.

All of the SimDB commands have help available via the CLI by using the `--help` argument, i.e.

```bash
simdb --help
```

Will print the top-level help, whereas

```bash
simdb simulation --help
```

Will print the help available for the `simulation` command.

## Local simulation management

In order to ingest a locat simulation you need a manifest file. This is a `yaml` file which contains details about the simulation and what data is associated with it.

An example manifest file is:

```yaml
version: 1
alias: my-simulation
inputs:
- uri: file:///my/input/file
- uri: imas:?shot=1000&run=0
outputs:
- uri: imas:?shot=1000&run=1
meta:
- values:
    workflow:
      name: Workflow Name
      git: ssh://git@git.iter.org/wf/workflow.git
      branch: master
      commit: 079e84d5ae8a0eec6dcf3819c98f3c05f48e952f
      codes:
        - Code 1:
            git: ssh://git@git.iter.org/eq/code.git
            commit: 079e84d5ae8a0eec6dcf3819c98f3c05f48e952f
```

| Key | Description |
| --- | --- |
| version | The version of the manifest file being written. This is to allow for legacy manifest files to be read, and should always be set to the latest version for newly created manifest files. The latest manifest version is 1. |
| alias | An optional entry which can be used to provide an alias for the simulation. This alias can also be provided via the CLI on ingest (see below). |
| inputs/outputs | Simulation inputs and outputs. The URIs that can be handled currently are: <ul><li>file - standard file URI</li><li>imas - IMAS entry URI (see below for schema)</li></ul> |
| meta |  The meta section is where any metadata about the simulation can be associated with the data. The entries in the meta section must be of the following: <ul><li>values - a nested dictionary of keys/value pairs</li><li>files - a file path which can be used to load an additional yaml file containing metadata.</li></ul> |

You can create a new manifest file to population using the command

```bash
simdb manifest create <FILE_NAME>
```

Once you have a manifest file ready you can ingest the simulation into SimDB using the following command:

```bash
simdb simulation ingest <MANIFEST_FILE>
```

If you have not provided an alias in the manifest file (or want to override the alias provided there) you can provide an alias for the simulation on ingest:

```bash
simdb simulation ingest --alias <ALIAS> <MANIFEST_FILE>
```

You can list all the simulations you have stored locally using:

```bash
simdb simulation list
```

and you can see all the stored metadata for a simulation using:

```bash
simdb simulation info <SIM_ID>
```

**Note:** Whenever a command takes a `<SIM_ID>` this can either be the full UUID of the simulation, the short UUID (the first 8 characters of the UUID), or the simulation alias.

### IMAS URI schema

The IMAS URI is used to locate a IMAS data entry. Currently, the query arguments are mapped to the existing DBEntry arguments.
```
imas:?database=<DATABASE>&pulse=<SHOT>&run=<RUN>&user=<USER>
```

## Remote SimDB servers

The SimDB CLI is able to interact with remote SimDB servers to push local simulations or to query existing simulations. This is done via the simdb remote command:

```bash
simdb remote --help
```

Configuring of SimDB remotes is done via the `config` subcommand:

```bash
simdb remote config --help
```

To see which remotes are available you can use the following:

```bash
simdb remote config list
```

To add a new remote you can use:

```bash
simdb remote config new <NAME> <URL>
```

i.e.

```bash
simdb remote config new ITER https://simdb.iter.org
```

In order to not have to specify the remote name when using any of the SimDB CLI remote subcommands you can set a remote to be default. The default remote will be used whenever the remote name is not explicitly passed to a remote subcommand. Setting a default remote can be done using:

```bash
simdb remote config set-default <NAME>
```

### Authentication

In order to interact with SimDB remote servers you must be authenticated against that server. By default, this is done using username/password which will need to be entered upon each remote command run. In order to reduce the number of times you have to manually enter your authentication details you can generate an authentication token from the server which is stored against that remote. While that token is valid (token lifetimes are determined on a per-server basis) you can run remote commands against that server without having to provide authentication details.

In order to generate a remote authentication token you need to run:

```bash
simdb remote token new
```

Running this command will require you to authenticate against the server as normal but once it has run it will store an authentication token against the remote so that you will not need to enter authentication credentials when running other remote commands.

You can delete a stored token by running:

```bash
simdb remote token delete
```

**Note:** All the commands in this section assume there is a default remote that has been set (see above) so omit the remote name in the command. If no default has been set then the remote name needs to be inserted into the command, i.e. `simdb remote <NAME> token new`.

## Pushing simulations to a remote

Once you have ingested your simulation locally and are happy with the metadata that has been stored alongside it, you may choose to push this simulation to a remote SimDB server to make it publicly available. You do this by:

```bash
simdb simulation push <SIM_ID>
```

This will upload all the metadata associated with your simulation to the remote server as well as taking copies of all input and output data specified. For non-IMAS data the `file` URIs will be used to locate the files to transfer, whereas for `imas` URIs SimDB will discover which files need to be transferred based on the IMAS backend specified in the URI. The files are copied to the server using an HTTP data transfer.

## Pulling simulations from a remote

The mirror to pushing simulations is the `pull` command. This command will pull the simulation metadata from the SimDB remote to your local SimDB database and download the simulation data into a directory of your choosing. Once you have pulled a simulation it will appear in any local SimDB queries you perform. The command looks as follows:

```bash
simdb simulation pull [REMOTE] <SIM_ID> <DIRECTORY>
```

The `REMOTE` argument is optional and if omitted will use your specified default remote. The `SIM_ID` is the alias or uuid of the simulation on the remote you wish to pull, and the `DIRECTORY` argument specifies the location you wish to download the data to.

## Querying remotes

You can query all the simulations available from a remote SimDB server using:

```bash
simdb remote list
```

and you can see all of the stored metadata against a remote simulation using:

```bash
simdb remote info <SIM_ID>
```