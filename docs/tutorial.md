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

The first step in ingesting a simulation is to create the manifest file. This is a YAML document that describes your simulation and its associated data.

### Quick Start

You can create a new manifest file template using the command:

```bash
simdb manifest create manifest.yaml
```

This generates a basic template that you can customize for your simulation.

### Manifest Structure Guidelines

**Manifest Version**

Always use the latest manifest version to ensure compatibility:
```yaml
manifest_version: 2
```

**Simulation Alias**

Provide a unique, descriptive identifier for your simulation:
```yaml
alias: iter-baseline-scenario-2024
```

Best Practices:
- Use descriptive names that indicate the simulation purpose
- Consider using a naming convention like `machine-scenario-date`
- Common patterns include: `pulse_number/run_number` (e.g., `100001/1`)
- Ensure uniqueness within your SimDB instance

**Input and Output Files**

Specify all data files associated with your simulation:

```yaml
inputs:
  - uri: file:///path/to/input/parameters.txt
  - uri: imas:hdf5?path=/work/imas/input_data
  
outputs:
  - uri: file:///path/to/results/output.nc
  - uri: imas:mdsplus?path=/work/imas/simulation_output
```

Guidelines:
- Use absolute paths for `file://` URIs
- For IMAS data, specify the correct backend (`hdf5` or `mdsplus`)
- Include all relevant input files (initial conditions, parameters, configuration)
- List all output files (results, diagnostics, visualizations)

**Metadata Section**

The metadata section contains descriptive information about your simulation:

```yaml
metadata:
  - machine: ITER
  - code:
      name: JETTO
      version: "2024.1"
  - description: |-
      Baseline H-mode scenario simulation for ITER
      15MA plasma current with Q=10 target
  - reference_name: ITER_Baseline_2024
  - ids_properties:
      creation_date: '2024-12-05 10:30:00'  
```

Metadata Best Practices:
- **machine**: Always specify the tokamak or device name
- **code**: Include both name and version for reproducibility
- **description**: Provide context about the simulation purpose and key features
- **reference_name**: Use a human-readable reference identifier
- **ids_properties**: Include creation date if not available in IDS data

### Validating a Manifest File

Before ingesting your manifest, it's important to validate it to ensure it's well-formed. SimDB provides a validation command:

```bash
simdb manifest check manifest.yaml
```

This command will check your manifest file for:
- Correct YAML syntax
- Required fields (manifest_version)
- Valid URI formats for inputs and outputs
- Proper metadata structure
- Alias naming rules compliance

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
simdb remote --new test https://simdb.iter.org/scenarios/api
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
