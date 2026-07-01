# SimDB simulation management tool

[![PyPI](https://img.shields.io/pypi/v/imas-simdb.svg)](https://pypi.org/project/imas-simdb/)
[![Documentation Status](https://readthedocs.org/projects/simdb/badge/?version=latest)](https://simdb.readthedocs.io/en/latest/)
[![CI](https://github.com/iterorganization/SimDB/actions/workflows/build_and_test.yml/badge.svg)](https://github.com/iterorganization/SimDB/actions)

---

## Overview

**SimDB** is a powerful tool designed to track, manage, upload, and query simulations. Simulation data can be tagged with metadata, managed locally, and seamlessly transferred to remote SimDB services. Uploaded simulations can then be queried based on metadata.

---

## Features

- **CLI Tool:** Intuitive command line tool for all major operations.
- **Metadata Tagging:** Associate simulations with flexible, searchable metadata.
- **Remote Sync:** Transfer data to/from remote SimDB servers.
- **Developer Friendly:** Easy setup for contributing & extending codebase.

---

## Quickstart

Install SimDB (requires Python 3.11+):

```bash
pip install imas-simdb
```

SimDB version:

```bash
simdb --version
simdb remote [NAME] version
```

Ingest and upload your first simulation:

```bash
simdb simulation ingest -a SIM_ID MANIFEST_FILE
simdb simulation push [REMOTE] SIM_ID
```

Query simulations by metadata:

```bash
simdb simulation query [OPTIONS] [CONSTRAINTS]
simdb remote [REMOTE] query [OPTIONS] [CONSTRAINTS]
```
_where:_
- `SIM_ID` — UUID or alias for your simulation  
- `REMOTE` — The remote server name (as configured locally)  
- `MANIFEST_FILE` — YAML document that describes your simulation and its associated data
- `OPTION` - Additional optional parameters for the given command (see `--help` output)

[See full installation guide in the documentation &rarr;](https://simdb.readthedocs.io/en/latest/install_guide.html)

---

## Command Line Interface

SimDB provides a CLI tool to manage your simulation workflow.  
To view help and subcommands:

```bash
simdb --help
```

[Full CLI usage reference &rarr;](https://simdb.readthedocs.io/en/latest/cli.html)

---

## Usage Examples

- Uploading data:
  ```bash
  simdb simulation ingest -a my_simulation my_sim_manifest.yaml
  simdb simulation push ITER my_simulation
  ```
- Querying simulations:
  ```bash
  simdb simulation query code.name=ITER
  simdb remote ITER query code.name=ITER
  alias     code.name  
  --------------------
  103027/3  SOLPS-ITER 
  103028/3  SOLPS-ITER
  ```

---

## Accessing ITER Remotes

To access data from the ITER remotes outside ITER systems, you'll need to [configure a SimDB remote](https://simdb.readthedocs.io/en/latest/iter_remotes.html).

---

## Server Setup

Setting up and maintaining a remote CLI server is documented [here](https://simdb.readthedocs.io/en/latest/maintenance_guide.html).

---

## Developer Guide

Want to contribute or run SimDB from source?  
[See the developer guide &rarr;](https://simdb.readthedocs.io/en/latest/developer_guide.html)

---

## License

The software is licensed under the **LGPLv3** License which allows for extensive freedom in using, modifying, and distributing it, provided that the license terms are met.
Details can be found in [LICENSE-LGPL](LICENSE.txt).

---

## Contact

- Issues & Feature Requests: [GitHub Issues](https://github.com/deepakmaroo/SimDB/issues)
- Documentation: [simdb.readthedocs.io](https://simdb.readthedocs.io/en/latest/)

---
