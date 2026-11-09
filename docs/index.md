# IMAS Simulation Database Management Tool

**SimDB** tracks, manages, validates and shares scientific simulations. You
describe a simulation and the data it produced in a small manifest file, ingest
it into your local catalogue, and, when you are ready, push it to a shared
SimDB server where colleagues can query, validate and reuse it.

SimDB is built for [IMAS](explanation/glossary.md) fusion-simulation workflows
but works with any files you want to catalogue.

## Where to start

- **Getting started**: [Install SimDB](getting-started/installation.md), then
  follow the [quickstart](getting-started/quickstart.md).
- **Tutorials**:
  [Catalogue your first simulation](tutorials/first-simulation.md), then
  [push it to a server](tutorials/push-to-remote.md).
- **How-to guides**: Task recipes for
  [manifests](how-to/create-a-manifest.md),
  [queries](how-to/query-simulations.md),
  [remotes](how-to/configure-remotes.md) and
  [running a server](how-to/operate-server/install-server.md).
- **Reference**: The [CLI](reference/cli.md),
  [configuration](reference/configuration.md),
  [manifest format](reference/manifest-format.md) and
  [Python API](reference/python-api/index.md).
- **Explanation**: Understand the [concepts](explanation/concepts.md) and
  [architecture](explanation/architecture.md) behind SimDB.

```{toctree}
:caption: Getting Started
:maxdepth: 2
:hidden:

getting-started/installation
getting-started/quickstart
```

```{toctree}
:caption: Tutorials
:maxdepth: 2
:hidden:

tutorials/first-simulation
tutorials/push-to-remote
```

```{toctree}
:caption: How-to Guides
:maxdepth: 2
:hidden:

how-to/create-a-manifest
how-to/ingest-and-manage
how-to/query-simulations
how-to/push-pull
how-to/validate-a-simulation
how-to/configure-remotes
how-to/authenticate
how-to/connect-to-iter
how-to/migrate-al4-mdsplus
how-to/use-the-dashboard
```

```{toctree}
:caption: Operating a Server
:maxdepth: 2
:hidden:

how-to/operate-server/install-server
how-to/operate-server/run-dev-server
how-to/operate-server/run-with-docker
how-to/operate-server/run-celery-workers
how-to/operate-server/run-multiple-instances
how-to/operate-server/run-behind-nginx-gunicorn
how-to/operate-server/enable-ssl
how-to/operate-server/set-up-postgresql
how-to/operate-server/configure-authentication
how-to/operate-server/configure-validation
```

```{toctree}
:caption: Contributing
:maxdepth: 2
:hidden:

how-to/contribute/set-up-dev-env
how-to/contribute/run-tests-and-lint
how-to/contribute/run-migrations
how-to/contribute/build-the-docs
```

```{toctree}
:caption: Reference
:maxdepth: 2
:hidden:

reference/cli
reference/configuration
reference/server-configuration
reference/manifest-format
reference/uri-schemes
reference/query-operators
reference/rest-api
reference/python-api/index
```

```{toctree}
:caption: Explanation
:maxdepth: 2
:hidden:

explanation/concepts
explanation/architecture
explanation/validation
explanation/glossary
```

```{toctree}
:caption: Help
:maxdepth: 1
:hidden:

troubleshooting
```
