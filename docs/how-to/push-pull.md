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

### Resumable uploads

Against a v1.3 remote, `push` sends the file bytes using the IETF
[Resumable Uploads for HTTP](https://datatracker.ietf.org/doc/draft-ietf-httpbis-resumable-upload/)
protocol (draft 11, interop version 8). No shared file system is required. The
server stages the uploaded bytes in its `http` partition, and from there the
flow matches `push_local`: SimDB sends the metadata, the server queues the copy
into its upload folder as a background
[Celery task](operate-server/run-celery-workers.md), and the CLI blocks while
reporting the ingestion state. Against a v1.2 remote, `push` falls back to the
earlier non-resumable transfer.

Because the protocol is resumable, an interrupted upload (a lost connection,
Ctrl-C) does not have to start over. Re-running `push` for the same simulation
asks the server how many bytes it already holds for each file and continues from
that offset.

The chunk size is governed by the server: it advertises a maximum append size
through the `Upload-Limit` response header and the client sizes its chunks to
stay within that bound. The limit defaults to 8 MiB and can be tuned with
[`server.max_append_size`](../reference/server-configuration.md#server), for
example to fit within a reverse proxy's request body limit.

Each chunk is integrity-checked with an RFC 9530 `Content-Digest` (SHA-256), so
the server can verify a chunk before appending it. A digest mismatch is rejected
with a `400` response and the offending bytes are not stored, so corruption in
transit cannot be silently committed.

### Stage uploads on the server

`push` needs no client-side partition configuration — the paths come straight
from the local simulation. The server, however, must define where uploaded bytes
are staged, through a partition named `http` in its `simdb.cfg` (see
[Server configuration](../reference/server-configuration.md#partition)):

```ini
[partition]
http = /var/lib/simdb/http-staging
```

A file uploaded to `<sim_uuid>/file/<path>` is written to
`<http partition>/<sim_uuid>/file/<path>` and referenced by an
`http:///<sim_uuid>/file/<path>` URI. The background ingestion task resolves that
URI against the `http` partition, copies the file into the simulation's upload
folder, and finally removes the staged copy.

Subfolder structure is handled just as it is for
[`push_local`](#push-on-a-shared-file-system): files keep their relative layout,
so multi-file IMAS datasets (HDF5, ASCII, and MDSplus backends) stay contained
within their own directory and are reconstructed correctly on the server, while
standalone files (such as an IMAS netCDF `.nc`) are not given a spurious
enclosing folder.

## Push on a shared file system

If your machine and the server can reach the same physical file paths (as on the
ITER network), sending large datasets over HTTP is slow and redundant. Use
`push_local` instead:

```bash
simdb simulation push_local SIM_ID
```

`push_local` sends only the metadata and the storage paths. The server then

1. validates the metadata against the active schemas,
2. queues the file copy as a background [Celery task](operate-server/run-celery-workers.md), and
3. completes the ingestion once the copy finishes.

The command blocks and reports the ingestion state as it changes:

```text
Waiting for ingestion to complete... QUEUED -> COPYING -> COPIED -> COMPLETED
Successfully pushed simulation UUID
```

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
