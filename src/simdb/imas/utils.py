import inspect
from typing import List, Any
from uri import URI


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


def remove_methods(obj) -> List[str]:
    members = inspect.getmembers(obj)
    names = []
    for member in members:
        if not member[0].startswith('__') and not callable(getattr(obj, member[0])) and member[0] != 'method':
            names.append(member[0])
    return names


def open_imas(uri: URI) -> Any:
    import os
    import imas
    shot = uri.query.get('shot')
    run = uri.query.get('run')
    user = uri.query.get('user', os.environ['USER'])
    machine = uri.query.get('machine')
    version = uri.query.get('version', '3')
    if not shot:
        raise KeyError('IDS shot not provided in URI ' + str(uri))
    if not run:
        raise KeyError('IDS run not provided in URI ' + str(uri))
    if not machine:
        raise KeyError('IDS machine not provided in URI ' + str(uri))
    ids = imas.ids(shot, run)
    ids.open_env(user, machine, version)
    return ids
