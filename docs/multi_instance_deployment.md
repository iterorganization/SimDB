# Running multiple SimDB server instances

Each deployment uses a dedicated Git worktree and Docker Compose project. Compose
project names isolate PostgreSQL, Redis, uploaded files, containers, and networks.
The management script only updates worktrees beneath `SIMDB_INSTANCE_ROOT`; it does
not modify the checkout from which it is invoked. All instances use
`docker-compose-dev.yml` and `Dockerfile.dev`; the production Compose and
Dockerfile are not used or modified.

## Requirements

- Docker with the Compose plugin
- Git access to the configured remote
- A clean source repository containing `scripts/simdb-instance`

The default instance directory is a sibling of the repository named
`simdb-instances`. Override it when required:

```bash
export SIMDB_INSTANCE_ROOT=/srv/simdb/instances
```

## Deploy environments

Keep `main` on port 5000 and `develop` on port 5100:

```bash
scripts/simdb-instance deploy-main
scripts/simdb-instance deploy-develop
```

Deploy a pull request. If no port is supplied, the first unused port in
5101-5999 is assigned:

```bash
scripts/simdb-instance deploy-pr 123
scripts/simdb-instance deploy-pr 124 --port 5124
```

Deploy any remote branch:

```bash
scripts/simdb-instance deploy-branch feature/query-cache
scripts/simdb-instance deploy-branch feature/query-cache \
    --name query-cache --port 5200
```

Updating an existing instance preserves its assigned port and named volumes.
Tracked changes inside a managed worktree are discarded because these worktrees
are deployment artifacts. Untracked runtime files are preserved.

## Inspect and remove environments

```bash
scripts/simdb-instance list
scripts/simdb-instance status pr-123
scripts/simdb-instance logs pr-123
scripts/simdb-instance stop pr-123
```

`stop` preserves PostgreSQL, Redis, and uploaded data. `destroy` permanently
removes them along with the managed worktree:

```bash
scripts/simdb-instance destroy pr-123
```

## Verify the deployed revision

Open the development-only identity endpoint:

```bash
curl http://localhost:5100/__simdb_instance
```

It returns:

```json
{
  "deployment": "pr-123",
  "git_branch": "pull/123",
  "git_commit": "81d992f...",
  "deployed_at": "2026-06-24T10:00:00Z"
}
```

The development Nginx proxy also adds `X-SimDB-Deployment`,
`X-SimDB-Branch`, `X-SimDB-Commit`, and `X-SimDB-Deployed-At` to every
response:

```bash
curl -I http://localhost:5100/
```

This identity behavior exists only in `docker-compose-dev.yml`; no SimDB Python
API code is changed.