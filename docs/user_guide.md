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

In order to ingest a local simulation you need a manifest file. This is a `yaml` file which contains details about the simulation and what data is associated with it.

An example manifest file is:

```yaml
manifest_version: 2
alias: simulation-alias
inputs:
- uri: file:///my/input/file
- uri: imas:hdf5?path=/path/to/imas/data
outputs:
- uri: imas:hdf5?path=/path/to/more/data
metadata:
- summary:
    machine: name of machine i.e. ITER.
    code:
      name: code name i.e. ASTRA, JETTO, DINA, CORSICA, MITES, SOLPS, JINTRAC etc.
    simulation:
      description: |-
      Sample plasma physics simulation for ITER tokamak modeling
      reference_name: ITER simulation
    ids_properties:
      creation_date: 'YYYY-MM-DD HH:mm:ss'
```

| Key | Description |
| --- | --- |
| manifest_version | The version of the manifest file format. Always use the latest version (currently 2) for new manifest files. This ensures compatibility and access to the latest features. |
| alias | An optional unique identifier for the simulation. If not provided here, you can specify it via the CLI during ingestion. Must follow alias naming rules (see below). |
| inputs/outputs | Lists of simulation input and output files. Supported URI schemes:<br/>• file - Standard file system paths<br/>• imas - IMAS entry URIs (see IMAS URI schema below) |
| metadata |  Contains simulation metadata and properties. The metadata section associates information with the summary IDS data:<br/>• summary - A hierarchical dictionary structure containing key-value pairs that provide summary information extracted from IDS datasets. This includes condensed representations of simulation results, computed quantities, free descriptions, any references, and creation dates if not available in summary IDS.</li>
<!-- <li>files - a file path which can be used to load an additional yaml file containing metadata.</li></ul>  -->

## Alias Naming Rules
<ul><li>Must be unique within the SimDB</ul></li>
<ul><li>Cannot start with a digit (0-9) or forward slash (/)</ul></li>
<ul><li>Cannot end with a forward slash (/)</ul></li>
<ul><li>Should be descriptive and meaningful for easy identification</ul></li>

<br/>Examples of valid aliases:
<ul><li>iter-baseline-scenario</ul></li>
<ul><li>100001/1 (pulse_number/run_number)</ul></li>

## Creating a Manifest File
You can create a new manifest file template using the command:

```bash
simdb manifest create <FILE_NAME>
```

Once you have a manifest file ready, you can ingest the simulation into SimDB using the following command:

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

> **Note**
> 
> All use of IMAS URIs require IMAS AL5 to be installed and available from SimDB. If using IMAS AL4 you'll need to use
> legacy URI syntax see below.

IMAS URIs specified in the manifest can either be in the form of remote data URIs or local data URIS.

The IMAS local data URI is used to locate an IMAS data entry accessible from the machine where the client
is being run. The URI schema looks like:

```
imas:<backend>?path=<path>
```

Where:

| Argument | Description                                               |
|----------|-----------------------------------------------------------|
| Backend  | The backend to use to open the files on the remote server |
| Path     | The path to the folder containing the IMAS data files     |

Some examples of local URIs are:

```text
imas:mdsplus?path=/work/imas/shared/imasdb/iter/3/135011/2
imas:hdf5?path=/work/imas/shared/imasdb/ITER_SCENARIOS/3/131002/60
```

When a local IMAS URI is pushed to the server the URI will be transformed into a remote data URI
so that it can be accessed from machines remote from the server.

The IMAS remote data URI is used to locate a remote IMAS data entry. The IMAS URI schema for remote data looks like:
```
imas://<server>:<port>/uda?path=<path>&backend=<backend>
```

Where:

| Argument | Description                                               |
|----------|-----------------------------------------------------------|
| Server   | The name of the remote data server i.e. uda.iter.org      |
| Port     | The port to connect to on the remote data server          |
| Path     | The path to the data files on the remote server           |
| Backend  | The backend to use to open the files on the remote server |

An example URI is

`imas://io-ls-uda01.iter.org:56565/uda?path=/work/imas/shared/imasdb/ITER/3/131024/51&backend=hdf5`

> **Legacy IMAS URIs**
> 
> If only IMAS AL4 is available on the machine where the SimDB client is running it is
> still possible to ingest IMAS data created with the HDF5 backend (HDF5 is the only supported backend).
> When this data is pushed to the server the URI will be converted into an AL5 remote data access URI.
> 
> The URI syntax for legacy data is:
> ```
> imas:?shot=<shot>&run=<run>&user=<user>&database=<database>&version=<version>&backend=<backend>
> ```
> 
> | Argument | Description                                                                                                                                   |
> |----------|-----------------------------------------------------------------------------------------------------------------------------------------------|
> | Shot     | The IMAS shot number                                                                                                                          |
> | Run      | The IMAS run number                                                                                                                           |
> | User     | The user (or path to imasdb) that the database lives in (or 'public' for the `$IMAS_HOME` database, defaults to current user if not provided) |
> | Database | The name of the database                                                                                                                      |
> | Version  | The IMAS version number (defaults to 3 if not provided)                                                                                       |
> | Backend  | The backend which is used to read the file                                                                                                    |
> 
> An example legacy URI is:
> 
> ```imas:?shot=30420&run=1&user=public&database=iter&version=3&backend=hdf5```

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

and you can see all the stored metadata against a remote simulation using:

```bash
simdb remote info <SIM_ID>
```