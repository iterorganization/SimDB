# Create a manifest

A [manifest](../reference/manifest-format.md) is the YAML file you ingest to
catalogue a simulation. Writing one is mostly a matter of listing the right
data and describing it well; that is what this guide covers. The
[manifest format reference](../reference/manifest-format.md) has the complete
specification of every field.

## Start from a template

```bash
simdb manifest create manifest.yaml
```

This writes a starter manifest you can edit.

## Set the version and alias

Always use version 2, and give the simulation a descriptive, unique, URL-safe
alias:

```yaml
manifest_version: 2
alias: iter-baseline-scenario-2024
```

Good alias conventions:

- a descriptive name such as `machine-scenario-date`; or
- a `pulse_number/run_number` form such as `100001/1`.

The alias is optional in the manifest; you can also set it at ingest time with
`simdb simulation ingest -a ALIAS`.

## List inputs and outputs

List every data file the simulation used (`inputs`) and produced (`outputs`),
as [URIs](../reference/uri-schemes.md):

```yaml
inputs:
  - uri: file:///work/sims/run42/input/parameters.txt
  - uri: imas:hdf5?path=/work/imas/input_data
outputs:
  - uri: file:///work/sims/run42/results/output.nc
  - uri: imas:mdsplus?path=/work/imas/simulation_output
```

Tips:

- Use absolute paths for `file` URIs. Glob patterns such as `*.nc` are expanded.
- For IMAS data, give the correct backend (`hdf5` or `mdsplus`).
- Include all relevant inputs (initial conditions, parameters, configuration)
  and all outputs (results, diagnostics).

## Describe it with metadata

```yaml
metadata:
  - machine: ITER
  - code:
      name: JETTO
      version: "2024.1"
  - description: |-
      Baseline H-mode scenario simulation for ITER.
      15 MA plasma current with a Q=10 target.
```

Conventions:

- **machine**: the device name. Always include it.
- **code**: name and version, for reproducibility.
- **description**: context about the run's purpose.
- Add any other key/value pairs you want to be able to query on. Metadata names
  may not contain `:`, `=`, or `#`.

## Check it

Before ingesting, validate the file's structure:

```bash
simdb manifest check manifest.yaml
```

Then ingest it (see [Ingest and manage simulations](ingest-and-manage.md)).
