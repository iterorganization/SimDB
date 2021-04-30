# SimDB Installation Guide

## Dependencies

The SimDB CLI has the following dependencies. All dependencies except for Python will be automatically installed via pip.

* Python (>= 3.6)
* argcomplete (>= 1.9.4)
* numpy (>= 1.14)
* python-dateutil (>= 2.6)
* pyyaml (>= 3.13)
* requests (>= 2.19.1)
* sqlalchemy (>= 1.2.12)
* urllib3 (>= 1.23)
* appdirs (>=1.4.0)
* uri (>=2.0)
* email-validator (>=1.1)
* semantic-version (>=2.8)
* click (>=7.0)
* Cerberus (>=1.3.2)
* distro (>=1.5.0)
* PyJWT (>=1.4.0)

## Installing simdb

Installing from source:

```
git clone ssh://git@git.iter.org/imex/simdb.git
pip3 install ./simdb
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
