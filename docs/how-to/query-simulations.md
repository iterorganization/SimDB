# Query simulations

You can search by metadata both in your local catalogue and on a remote server.
The common cases are shown below; for the full operator list and syntax, see
[Query operators](../reference/query-operators.md).

## Query locally

```bash
simdb simulation query code.name=JETTO
simdb simulation query global_quantities.r0.value=gt:6 machine=ITER
```

Each constraint is `NAME=[modifier:]VALUE`. Multiple constraints are combined
with AND. Add metadata columns with `-m` and UUIDs with `--uuid`:

```bash
simdb simulation query machine=ITER -m code.name --uuid
```

## Query a remote

The same syntax works against a server:

```bash
simdb remote query machine=ITER
simdb remote iter query code.name=SOLPS-ITER
```

If you have set a default remote, omit its name. Example output:

```text
alias     code.name
--------------------
103027/3  SOLPS-ITER
103028/3  SOLPS-ITER
```

## Browse a remote

List everything on a remote, or inspect one simulation:

```bash
simdb remote list
simdb remote info SIM_ID
```

## Inspect IDS data from a remote simulation

`simdb simulation data` reads a single populated IDS field from the IMAS output
attached to a remote simulation:

```bash
simdb simulation data [REMOTE] SIM_ID IDS_PATH
```

`REMOTE` is the configured remote name, and defaults to the default remote when
omitted. `SIM_ID` is either the simulation UUID or its alias, for example
`53301/2`. `IDS_PATH` has the form `ids_name[:occurrence]/path/to/field`:

```bash
simdb simulation data pr-70 '53301/2' \
  'summary:0/global_quantities/li_3/value' \
  --dd-version 4.1.1
```

The command prints the simulation UUID, the requested path, the occurrence, and
the field value with its units and coordinates where available. One-dimensional
numeric fields also get a terminal plot and a summary panel.

`--dd-version` asks the server to convert the IDS to that IMAS Data Dictionary
version before resolving the path, which matters when a field was renamed
between versions. Data stored with DD `3.42.0` may hold
`global_quantities/li/value`, while DD `4.1.1` exposes the same quantity as
`global_quantities/li_3/value`.

The equivalent REST call is
`GET /v1.3/simulation/{SIM_ID}/data?path={IDS_PATH}[&dd_version={DD_VERSION}]`;
see the [REST API reference](../reference/rest-api.md).

## Common operators

| Constraint | Matches |
| --- | --- |
| `machine=ITER` | exactly `ITER` (case-insensitive) |
| `code.name=in:sol` | values containing `sol` |
| `global_quantities.r0.value=gt:6` | values greater than 6 |
| `sequence=exist:` | simulations that have a `sequence` field |

See [Query operators](../reference/query-operators.md) for the rest.
