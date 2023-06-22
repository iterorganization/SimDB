import inspect
import multiprocessing as mp
from typing import List, Any
from datetime import datetime
from pathlib import Path

from ..uri import URI


class ImasError(Exception):
    pass


def get_metadata(imas_obj) -> dict:
    ids = getattr(imas_obj, "dataset_description")
    ids.get()

    metadata = dict(
        imas_version=ids.imas_version,
        dd_version=ids.dd_version,
        provider=ids.ids_properties.provider,
        user=ids.data_entry.user,
        creation_date=ids.ids_properties.creation_date,
    )

    return metadata


FLOAT_MISSING_VALUE = -9.0e40
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


def list_idss(entry) -> List[str]:
    import imas
    from imas import imasdef

    idss = []
    for name in imas.IDSName:
        value = entry.partial_get(name.value, "ids_properties/homogeneous_time")
        if value != imasdef.EMPTY_INT:
            idss.append(name.value)
    return idss


def check_time(entry, ids) -> None:
    from imas import imasdef

    homo_time = entry.partial_get(ids, "ids_properties/homogeneous_time")
    if homo_time == imasdef.IDS_TIME_MODE_HOMOGENEOUS:
        time = entry.partial_get(ids, "time")
        if time is None or time.size == 0:
            raise ValueError(
                f"IDS {ids} has homogeneous_time flag set to IDS_TIME_MODE_HOMOGENEOUS but invalid time entry."
            )


def remove_methods(obj) -> List[str]:
    members = inspect.getmembers(obj)
    names = []
    for member in members:
        if (
            not member[0].startswith("__")
            and not callable(getattr(obj, member[0]))
            and member[0] != "method"
        ):
            names.append(member[0])
    return names


def open_imas(uri: URI, create=False) -> Any:
    import imas

    if uri.scheme != "imas":
        raise ValueError(f"invalid imas URI: {uri} - invalid scheme")

    if uri.query is not None:
        try:
            path = uri.query.get("path")
        except KeyError:
            raise ValueError(f"invalid imas URI: {uri} - no path found in query")
    else:
        raise ValueError(f"invalid imas URI: {uri} - no query found in URI")

    entry = imas.DBEntry(str(uri))

    if create:
        if not Path(path).exists():
            Path(path).mkdir(parents=True, exist_ok=True)
        (status, _) = entry.create()
        if status != 0:
            raise ImasError(f"failed to create IMAS data with URI {uri}")
    else:
        (status, _) = entry.open()
        if status != 0:
            raise ImasError(f"failed to open IMAS data with URI {uri}")
    return entry


def imas_timestamp(uri: URI) -> datetime:
    entry = open_imas(uri)
    creation = entry.partial_get("summary", "ids_properties/creation_date")
    if creation:
        formats = [
            "%Y-%m-%d %H:%M:%S.%f",
            "%d/%m/%Y %H:%M",
            "%Y%m%d %H%M%S.%f %z",
        ]
        for format in formats:
            try:
                timestamp = datetime.strptime(creation, format)
                break
            except ValueError:
                pass
        else:
            raise ValueError(f"invalid IMAS creation time {creation}")
    else:
        timestamp = datetime.now()
    entry.close()
    return timestamp


def _copy_imas(from_uri, to_uri, ids_name):
    from_entry = open_imas(from_uri)
    to_entry = open_imas(to_uri)
    ids = from_entry.get(ids_name)
    to_entry.put(ids)
    from_entry.close()
    to_entry.close()


def copy_imas(from_uri: URI, to_uri: URI):
    from_entry = open_imas(from_uri)
    to_entry = open_imas(to_uri, create=True)
    idss = list_idss(from_entry)
    from_entry.close()
    to_entry.close()

    for ids in idss:
        print(f"Copying {ids}", flush=True)
        p = mp.Process(target=_copy_imas, args=(from_uri, to_uri, ids))
        p.start()
        p.join()
