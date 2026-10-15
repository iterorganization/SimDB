# Run background workers

SimDB uses [Celery](https://docs.celeryq.dev/) to run long operations outside the
HTTP request. When a simulation is uploaded through the REST API, the server
queues the file copying and the rest of the ingestion pipeline as background
tasks instead of blocking the client.

## Prerequisites

- SimDB [installed with the server extra](install-server.md).
- A message broker reachable from the server and the workers. Redis is the
  default: see the [`[celery]` options](../../reference/server-configuration.md)
  in `app.cfg`.

## Start a worker

```bash
simdb_worker
```

Periodic tasks, including the sweep that recovers stuck ingestions, need the
beat scheduler alongside the worker:

```bash
# Terminal 1: worker
simdb_worker

# Terminal 2: beat scheduler
simdb_beat
```

Under Docker Compose these run as the optional `worker` and `beat` services:
see [Run with Docker](run-with-docker.md).

## Monitor tasks

[Flower](https://flower.readthedocs.io/) provides a web UI for queued, running,
and failed tasks:

```bash
celery -A simdb.workers.celery flower --port=5555
```

## Tasks

| Task | Purpose |
| --- | --- |
| `copy_files_task` | Copies input and output files to the server's upload folder and updates the ingestion status. |
| `validate_imas_task` | Validates the metadata and, with a file validator configured, the output files of the copied simulation. Only queued when `auto_validate` is set: see [Configure validation](configure-validation.md). |
| `complete_ingestion_task` | Marks a simulation as fully ingested. |
| `send_email_task` | Sends email notifications. |
| `fail_stale_ingestions_task` | Periodic sweep that fails simulations stuck in a non-terminal ingestion state. |

## Recover stuck ingestions

A simulation moves through non-terminal ingestion states (`QUEUED`, `COPYING`,
`COPIED`, `VALIDATING`, `VALIDATED`) before reaching a terminal one
(`COMPLETED`, `COPY_FAILED`, `VALIDATION_FAILED`), and it can only be deleted
once it reaches a terminal state. The reason for a failed state is stored with
the simulation and returned by the status endpoint. Three mechanisms keep a
simulation from getting stuck:

1. A task that raises is caught, and the simulation is marked `COPY_FAILED` (or
   `VALIDATION_FAILED` when validation fails with `error_on_fail` set).
2. A task that hangs is stopped by `task_soft_time_limit` and then marked
   `COPY_FAILED`. The hard `task_time_limit` is an absolute backstop.
3. A worker that is hard-killed (SIGKILL, out of memory, node reboot) never runs
   its error handling, so `fail_stale_ingestions_task` sweeps up any simulation
   left in a non-terminal state for longer than `stale_ingestion_timeout`. This
   requires the beat scheduler to be running.

The sweep uses the `ingestion_status_updated_at` column, which is refreshed on
every update, so it reflects how long a simulation has been in its current
state.

As a manual fallback, an admin can force-delete a stuck simulation whatever its
ingestion state:

```text
DELETE /v1.3/simulation/<uuid>?force=true
```

## Run tasks synchronously

Setting `task_always_eager = True` runs tasks in-process without a broker, which
is how the test suite exercises the ingestion pipeline.
