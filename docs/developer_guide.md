# Developer Guide

## Setting up devloper environment

Checking out develop branch of SimDB:

```bash
git clone ssh://git@git.iter.org/imex/simdb.git
cd simdb
git checkout develop
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Installing server dependencies:

```bash
pip3 install -r requirements.txt
```

Installing editable version of SimDB:

```bash
pip3 install -e .
```

## Running the tests

In the SimDB root directory run:

```bash
pytest
```

## Running a development server

```bash
simdb_server
```

This will start a server on port 5000. You can test this server is running by opening htpp://localhost:5000 in a browser.