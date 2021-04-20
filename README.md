# SimDB simulation management tool

SimDB is a tool designed to track, manage, upload and query simulations. The simulation data can be tagged with metadata, managed locally or transferred to remote SimDB services. Uploaded simulations can then be queried based on metadata.

SimDB consists of a command line interface (CLI) tool which interacts with one or more remote services.

For details on how to install the CLI see [here](docs/install_guide.md) and for information on how to use the CLI see [here](docs/user_guide.md).

For information on setting and maintaining a remote CLI server see [here](docs/maintaintence_guide.md).

## CLI



### Installing the CLI

```bash
pip install git+ssh://git@git.iter.org/imex/simdb.git
```

## Remote API

* Python >= 3.6
* SqlAlchemy >= 1.2.2
* Flask >= 0.12.2
* PostgreSQL >= 9.6
* psycopg2-binary >= 2.7.4

## User Guide

The user guide is available at [here](./docs/user_guide.md).

## Server Setup Guide

The guide for installation of the server is available at [install Guide](./docs/install_guide.md)

## TODO

* Add remote modify
* Add remote query
* Add progress meter to file uploads
