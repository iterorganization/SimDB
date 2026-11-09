# Tutorial: catalogue your first simulation

By the end of this tutorial you will have written a manifest, checked it, and
ingested your first simulation into your local catalogue. All you need to start
is SimDB [installed](../getting-started/installation.md). When you are done,
continue with [Push your simulation to a server](push-to-remote.md).

## Step 1: check the CLI

Confirm SimDB is available:

```bash
simdb --version
```

You should see something like `simdb, version 0.15.2`. Every command has help
available with `--help`, at any level:

```bash
simdb --help
simdb simulation --help
```

The top-level help lists the command groups:

```text
Commands:
  config      Query/update application configuration.
  manifest    Create/check manifest file.
  remote      Interact with the remote SimDB service.
  simulation  Manage ingested simulations.
```

`sim` is an alias for `simulation`.

## Step 2: create a manifest

A simulation is described by a [manifest](../reference/manifest-format.md): a
YAML file listing the data the simulation used and produced, plus metadata about
it. Generate a starter template:

```bash
simdb manifest create manifest.yaml
```

Open `manifest.yaml` and fill it in. A complete example:

```yaml
manifest_version: 2
alias: iter-baseline-scenario-2024
inputs:
  - uri: file:///work/sims/run42/input/parameters.txt
  - uri: imas:hdf5?path=/work/imas/input_data
outputs:
  - uri: file:///work/sims/run42/results/output.nc
  - uri: imas:mdsplus?path=/work/imas/simulation_output
metadata:
  - machine: ITER
  - code:
      name: JETTO
      version: "2024.1"
  - description: |-
      Baseline H-mode scenario simulation for ITER.
      15 MA plasma current with a Q=10 target.
```

A few things to know (the [how-to](../how-to/create-a-manifest.md) and
[reference](../reference/manifest-format.md) cover them in full):

- Always use `manifest_version: 2`.
- The `alias` is optional but recommended; it must be unique and URL-safe.
- `inputs` and `outputs` use `file` and `imas`
  [URIs](../reference/uri-schemes.md). `file` paths must be absolute; glob
  patterns are expanded.
- `machine`, `code`, and `description` are the conventional metadata fields.

## Step 3: validate the manifest

Before ingesting, check the file is well-formed:

```bash
simdb manifest check manifest.yaml
```

This checks the YAML syntax, the required sections, the URI formats, the
metadata structure, and the alias rules. Fix any reported problems.

## Step 4: ingest the simulation

```bash
simdb simulation ingest manifest.yaml
```

This adds the simulation to your local catalogue, computing a checksum for each
referenced file. To override the manifest's alias at ingest time:

```bash
simdb simulation ingest -a my-alias manifest.yaml
```

## Step 5: inspect what you ingested

List your local simulations:

```bash
simdb simulation list
```

And show the full detail of one, by alias or UUID:

```bash
simdb simulation info iter-baseline-scenario-2024
```

## Where next

Your simulation is now catalogued: manifest written, checked, ingested, and
inspected, all locally. The next step is to share it:
[Push your simulation to a server](push-to-remote.md).
