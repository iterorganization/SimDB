# Push and pull simulations

Pushing copies a local simulation up to a server; pulling copies a server
simulation down to your machine. Both need a [configured remote](configure-remotes.md).

## Push

Once a simulation is ingested locally and you are happy with its metadata, push
it to make it available to others:

```bash
simdb simulation push SIM_ID
```

This uploads all metadata and copies every referenced input and output. For
`file` URIs the files are transferred directly; for `imas` URIs SimDB discovers
the files to transfer from the backend in the URI. Files are sent over HTTP.

Validate first to catch problems early (see
[Validate a simulation](validate-a-simulation.md)):

```bash
simdb simulation validate SIM_ID
```

### Replace an earlier simulation

```bash
simdb simulation push SIM_ID --replaces OLD_SIM_ID
```

The previous simulation is marked `deprecated` and gains a `replaced_by`
reference to the new one. Inspect the revision history with
`simdb remote trace SIM_ID`.

### Add a watcher while pushing

```bash
simdb simulation push SIM_ID --add-watcher
```

See [watchers](../explanation/concepts.md#watchers) and the
`simdb remote watcher` commands in the [CLI reference](../reference/cli.md).

## Push on a shared file system

If your machine and the server can reach the same physical file paths (as on the
ITER network), sending large datasets over HTTP is slow and redundant. Use
`push_local` instead:

```bash
simdb simulation push_local SIM_ID
```

`push_local` sends only the metadata and the storage paths. The server then

1. validates the metadata against the active schemas,
2. queues the file copy as a background [Celery task](operate-server/run-celery-workers.md),
3. validates the copied simulation, if the server is
   [configured to validate uploads](operate-server/configure-validation.md), and
4. completes the ingestion once these steps finish.

The command blocks and reports the ingestion state as it changes:

```text
Waiting for ingestion to complete... QUEUED -> COPYING -> COPIED -> VALIDATING -> VALIDATED -> COMPLETED
Successfully pushed simulation UUID
```

The `VALIDATING` and `VALIDATED` states only appear when the server validates
uploads. Server-side validation runs the metadata schemas again and, when the
server has a [file validator](../explanation/validation.md#file-content-validation)
such as the IMAS-Validator configured, checks the contents of the output files.
When validation fails the server records the reason and the command reports it:
with `error_on_fail` set on the server the ingestion ends in `VALIDATION_FAILED`
and the command fails, otherwise the simulation is ingested with a failed
validation status and the command prints the reason as a warning.

### Configure partitions

For `push_local` to resolve files on both sides, client and server must agree on
a set of *partitions*: short logical names mapped to absolute directories. Add a
`[partition]` section to your client configuration (see
[Client configuration](../reference/configuration.md#partition)):

```ini
[partition]
data = /home/user/my_simdb_data
work = /work/imas/shared
sdcc = /
```

Mapping `sdcc` to the system root makes any path under `/sdcc/projects/...`
match, so `/sdcc/projects/my_run` becomes `sdcc:sdcc/projects/my_run`. When
several partitions contain a file the most specific (deepest) path wins, so a
catch-all mapping like this never shadows the others.

When you run `push_local`, SimDB checks every input and output path against your
partitions. A path inside a partition is rewritten to a partition-relative URI —
`/home/user/my_simdb_data/scenarios/run1.txt` becomes
`data:scenarios/run1.txt`. The server resolves that URI against its own
`[partition]` configuration, so the two sides may mount the same storage at
different absolute paths.

## Pull

Pull copies a simulation's metadata into your local catalogue and downloads its
data into a directory you choose:

```bash
simdb simulation pull REMOTE SIM_ID DIRECTORY
```

- `REMOTE` is optional; the default remote is used if omitted.
- `SIM_ID` is the alias or UUID on the remote.
- `DIRECTORY` is where the data is downloaded.

After pulling, the simulation appears in your local
[queries](query-simulations.md).
