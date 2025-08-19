# SimDB Installation Guide

## Installing simdb

### Installing from source:

```
git clone git@github.com:iterorganization/SimDB.git
cd simdb
python3 -m venv ./venv
. venv/bin/activate
pip3 install -e .
```

### Installing directly from git:

```
pip3 install git@github.com:iterorganization/SimDB.git
```

### installing all dependencies (server, imas-validator, database):
```
pip3 install -e .[all]
```

## Installing simdb with specific extras:
### Install IMAS-Validator
```
pip3 install -e .[imas-validator]
```

### Install simdb server dependencies
```
pip3 install -e .[server]
```

### Install PostgreSQL support
```
pip3 install -e .[postgres]
```

### Install authentication dependencies
```
pip3 install -e .[auth-ldap]
pip3 install -e .[auth-keycloak]
pip3 install -e .[auth-ad]
```

### Install documentation dependencies
```
pip3 install -e .[build-docs]
```

### Multiple extras can be combined
```
pip3 install -e .[server,postgres,imas-validator]
```

You should then be able to run the command:

```
simdb --help
```

**Note:** If you get an error such as `command not found: simdb` then you may need to add the bin folder in your pip install location to your path.
