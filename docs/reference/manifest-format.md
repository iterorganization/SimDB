# Manifest format

A **manifest** is a YAML file that describes one simulation: a human-readable
alias, the input and output data it is associated with, and free-form metadata.
You ingest a manifest with `simdb simulation ingest` to add the simulation to
your local catalogue.

For a step-by-step guide to writing one, see
[Create a manifest](../how-to/create-a-manifest.md). To generate a starter file,
run `simdb manifest create manifest.yaml`, and to check a file run
`simdb manifest check manifest.yaml`.

## Example

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
responsible_name: j.smith
```

## Top-level sections

Only the sections listed below are allowed. Any other top-level key is a
validation error.

| Section | Required | Description |
| --- | --- | --- |
| `manifest_version` | Yes | Manifest format version. Must be the integer `2`. If omitted, version 2 is assumed (with a warning). |
| `inputs` | Yes | List of input data objects (see [Inputs and outputs](#inputs-and-outputs)). May be empty. |
| `outputs` | Yes | List of output data objects. May be empty. |
| `alias` | No | Human-readable name for the simulation (see [Alias](#alias)). |
| `metadata` | No | List of metadata name/value pairs (see [Metadata](#metadata)). |
| `responsible_name` | No | Name of the person responsible for the simulation. |

```{note}
Earlier manifest versions (0 and 1) used `path`/`imas`/`uuid` keys and a
`workflow` section. SimDB only ingests version 2 manifests. Rewrite any older
manifest in the version 2 form shown above.
```

## Inputs and outputs

`inputs` and `outputs` are each a list of single-entry mappings with a `uri`
key:

```yaml
inputs:
  - uri: file:///absolute/path/to/file
  - uri: imas:hdf5?path=/path/to/imas/data
```

Rules:

- Only the `file` and `imas` URI schemes are allowed. See
  [URI schemes](uri-schemes.md) for the full syntax.
- `file` paths must be absolute. Glob patterns are expanded, so
  `file:///data/run42/*.nc` adds every matching file. The variables
  `$MANIFEST_DIR` (the directory containing the manifest) and `~` are expanded.
- Duplicate URIs within the same section are rejected.

When a simulation is pushed to a server, SimDB locates the files behind these
URIs, checksums them, and transfers copies to the server.

## Alias

The alias is an optional, human-readable identifier. Rules:

- It must be unique within a given SimDB instance.
- It must be URL-safe: it may not contain characters that change when
  percent-encoded (for example spaces, `#`, `%`, `?`, `=`, `,`, `*`, `(`, `)`).
- By convention it is descriptive, for example `iter-baseline-scenario` or a
  `pulse_number/run_number` form such as `100001/1`.
- Once a simulation has been pushed to a server its alias is fixed.

You can set the alias in the manifest, or override it at ingest time with
`simdb simulation ingest -a ALIAS manifest.yaml`.

## Metadata

`metadata` is a list of single name/value pairs. Values may be scalars or
nested mappings:

```yaml
metadata:
  - machine: ITER
  - code:
      name: SOLPS-ITER
      version: "3.0.8"
  - description: Free-text description of the run.
  - pulse: 100001
```

Rules and conventions:

- Each list item must be a single name/value pair.
- Metadata names may not contain the characters `:`, `=`, or `#`, because these
  are used by the [query syntax](query-operators.md).
- `machine`, `code`, and `description` are the conventional fields and are
  expected by most servers; include them for every simulation.
- Servers can require additional metadata through a validation schema. Check a
  server's requirements with `simdb remote SERVER schema` and validate before
  pushing with `simdb simulation validate`. See
  [Validate a simulation](../how-to/validate-a-simulation.md).

Metadata is stored alongside the simulation and is what you search on with
[`simdb simulation query` and `simdb remote query`](query-operators.md).
