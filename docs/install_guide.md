# SimDB Installation Guide

## Installing simdb

Installing from source:

```
git clone ssh://git@git.iter.org/imex/simdb.git
cd simdb
pip3 install .
```

Installing directly from git:

```
pip3 install git+ssh://git@git.iter.org/imex/simdb.git@master
```

You should then be able to run the command:

```
simdb --help
```

**Note:** If you get an error such as `command not found: simdb` then you may need to add the bin folder in your pip install location to your path.
