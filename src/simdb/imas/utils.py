import inspect
from typing import List, Any
from uri import URI
from datetime import datetime
from pathlib import Path


class ImasError(Exception):
    pass


def get_metadata(imas_obj) -> dict:

    ids = getattr(imas_obj, 'dataset_description')
    ids.get()

    metadata = dict(
        imas_version=ids.imas_version,
        dd_version=ids.dd_version,
        provider=ids.ids_properties.provider,
        user=ids.data_entry.user,
        creation_date=ids.ids_properties.creation_date
    )

    return metadata


FLOAT_MISSING_VALUE = -9.0E40
INT_MISSING_VALUE = -999999999


def is_missing(value):
    if not value:
        return True

    dtype = type(value).__name__

    if dtype.startswith("float") and value == FLOAT_MISSING_VALUE:
        return True
    if dtype.startswith("str") and len(value) == 0:
        return True
    if dtype.startswith("int") and value == INT_MISSING_VALUE:
        return True

    if dtype == "ndarray" and value.size > 0:
        if dtype.startswith("float"):
            for num in value.data:
                if num == FLOAT_MISSING_VALUE:
                    return True
            for num in value.data:
                if num == FLOAT_MISSING_VALUE:
                    return True
        if dtype.startswith("int"):
            for num in value.data:
                if num == INT_MISSING_VALUE:
                    return True

    return False


def list_idss(imas_obj) -> List[str]:
    idss = []
    for name in (i for i in dir(imas_obj) if not i.startswith('_')):
        if '%s.%s' % (name, name) in str(type(getattr(imas_obj, name))):
            ids = getattr(imas_obj, name)
            ids.get()
            if not is_missing(ids.ids_properties.homogeneous_time):
                idss.append(name)
    return idss


def remove_methods(obj) -> List[str]:
    members = inspect.getmembers(obj)
    names = []
    for member in members:
        if not member[0].startswith('__') and not callable(getattr(obj, member[0])) and member[0] != 'method':
            names.append(member[0])
    return names


def open_imas(uri: URI, create=False) -> Any:
    import os
    import imas
    if uri.scheme != "imas":
        raise ValueError("invalid imas URI scheme: %s" % uri.scheme)
    shot = int(uri.query.get('shot'))
    run = int(uri.query.get('run'))
    user = uri.query.get('user', os.environ['USER'])
    path = uri.query.get('path')
    machine = uri.query.get('machine')
    version = uri.query.get('version', '3')
    if not shot:
        raise KeyError('IDS shot not provided in URI ' + str(uri))
    if not run:
        raise KeyError('IDS run not provided in URI ' + str(uri))
    if not machine:
        raise KeyError('IDS machine not provided in URI ' + str(uri))
    imas_obj = imas.ids(shot, run)
    if create:
        if Path(path).exists():
            (Path(path) / machine / '3' / '0').mkdir(parents=True)
        (status, _) = imas_obj.create_env(path if path else user, machine, version)
        if status != 0:
            raise ImasError("failed to create IMAS data with URI {}".format(uri))
    else:
        (status, _) = imas_obj.open_env(path if path else user, machine, version)
        if status != 0:
            raise ImasError("failed to open IMAS data with URI {}".format(uri))
    return imas_obj


def imas_timestamp(uri: URI) -> datetime:
    imas_obj = open_imas(uri)
    imas_obj.summary.get()
    creation = imas_obj.summary.ids_properties.creation_date
    if creation:
        creation = datetime.strptime(creation, '%Y-%m-%d %H:%M:%S.%f')
    else:
        creation = datetime.now()
    return creation


def copy_imas(from_uri, to_uri):
    from_obj = open_imas(from_uri)
    to_obj = open_imas(to_uri, create=True)
    idss = list_idss(from_obj)
    for ids in idss:
        getattr(from_obj, ids).get()
        getattr(to_obj, ids).copyValues(getattr(from_obj, ids))
        getattr(to_obj, ids).put()
