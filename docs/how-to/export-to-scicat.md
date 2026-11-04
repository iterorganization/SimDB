# Export simulations to SciCat

`simdb remote scicat-export` copies the metadata of every simulation on a
SimDB server into a [SciCat](https://scicatproject.github.io/) catalogue. No
data files are copied; SciCat records where they are stored.

## Install

The exporter needs [Scitacean](https://www.scicat-project.org/scitacean/), which
needs Python 3.10 or newer:

```bash
pip install 'imas-simdb[scicat]'
```

## Run the export

Get an API token from your SciCat instance, then:

```bash
export SCICAT_TOKEN=...
simdb remote iter scicat-export \
    --scicat-url https://scicat.example.org/api/v3 \
    --owner-group imas \
    --contact-email imas-support@iter.org \
    --dry-run
```

`--dry-run` maps and validates every simulation without uploading anything.
Drop it to do the export. The command prints how many simulations were
exported, skipped and failed, and exits with status 1 if any failed.

Other options:

- `--owner`: SciCat `owner` for every dataset. By default each simulation's
  `uploaded_by` metadata is used.
- `--access-group`: add a SciCat `accessGroups` entry. Repeat for several groups.
- `--source-folder-host`: SciCat `sourceFolderHost`, e.g. the storage cluster.
- `--limit N`: export only N simulations (default 0, which means all).

## What is exported

Each simulation becomes one SciCat **derived** dataset:

| SciCat field | Taken from |
|---|---|
| `datasetName` | alias, or the UUID if there is no alias |
| `description` | `description` metadata |
| `owner` | `--owner`, else `uploaded_by` metadata |
| `creationTime` | simulation date |
| `sourceFolder` | deepest directory containing all outputs (inputs if there are no outputs) |
| `inputDatasets` | SciCat PIDs of the simulation's parents |
| `usedSoftware` | `code.name` and `code.version` metadata |
| `dataFormat` | `IMAS` if any output is IMAS data |
| `keywords` | `simdb` and `simdb:<uuid>` |
| `scientificMetadata` | all SimDB metadata, nested on `.`; ranges stay `{min, max}` |
| `scientificMetadata.simdb` | UUID, alias, server URL, input and output URIs, parent UUIDs |

SciCat assigns its own PIDs, so the SimDB UUID is kept in
`scientificMetadata.simdb.uuid` and in the `simdb:<uuid>` keyword.

## Running it again

Before uploading a simulation, the exporter looks for a dataset with its
`simdb:<uuid>` keyword and skips it if one exists. Re-running the export only
adds new simulations; it does not update datasets that were exported earlier.

Parents are exported before their children, so a child's `inputDatasets` can
point at them. A parent that failed to export is left out of its child's
`inputDatasets`.
