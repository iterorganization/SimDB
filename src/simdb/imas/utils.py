import multiprocessing as mp
import os
from typing import List, Any
from datetime import datetime
from pathlib import Path

from ..uri import URI, Authority
from ..config import Config


class ImasError(Exception):
    pass


FLOAT_MISSING_VALUE = -9.0e40
INT_MISSING_VALUE = -999999999


def is_missing(value: Any):
    """
    Returns whether the given value is one of IMASs 'missing' values.

    @param value: the value to check
    @return: whether this value is 'missing'
    """
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


class DBEntry:
    def partial_get(self, ids: str, path: str) -> Any:
        ...


def list_idss(entry: DBEntry) -> List[str]:
    """
    List all the IDSs found to be populated for the given IMAS data entry.

    Each IDS is defined as being non-empty if the ids_properties/homogeneous_time field has been populated.

    @param entry: the IMAS data entry
    @return: the list of found IDSs
    """
    import imas
    from imas import imasdef

    idss = []
    for name in imas.IDSName:
        value = entry.partial_get(name.value, "ids_properties/homogeneous_time")
        if value != imasdef.EMPTY_INT:
            idss.append(name.value)
    return idss


def check_time(entry: DBEntry, ids: str) -> None:
    """
    Check the validity of the ids_properties/homogeneous_time field of the given IDS.

    @param entry: the open IMAS data entry
    @param ids: the
    @return:
    """
    from imas import imasdef

    homo_time = entry.partial_get(ids, "ids_properties/homogeneous_time")
    if homo_time == imasdef.IDS_TIME_MODE_HOMOGENEOUS:
        time = entry.partial_get(ids, "time")
        if time is None or time.size == 0:
            raise ValueError(
                f"IDS {ids} has homogeneous_time flag set to IDS_TIME_MODE_HOMOGENEOUS but invalid time entry."
            )


def open_imas(uri: URI, create=False) -> DBEntry:
    """
    Open an IMAS URI and return the IMAS entry object.

    @param uri: the IMAS URI to open
    @param create: whether to open the file in 'open' mode (False) or 'create' mode (True)
    @return: the IMAS data entry object
    """
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
    """
    Extract the timestamp from the IDS data for the given IMAS URI.

    @param uri: the IMAS URI
    @return: the timestamp as a datetime object
    """
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
    """
    Copy data from one IMAS URI to another.

    @param from_uri: the URI to copy from
    @param to_uri: the URI to copy to
    """
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


def _get_path_for_legacy_uri(uri: URI) -> Path:
    user = uri.query.get("user", default=None)
    database = uri.query.get("database", default=None)
    version = uri.query.get("version", default="3")
    shot = uri.query.get("shot", default=None)
    run = uri.query.get("run", default=None)
    if any(x is None for x in [user, database, shot, run]):
        raise ValueError(f"Invalid legacy URI {uri}")
    if user == "public":
        imas_home = os.environ.get("IMAS_HOME", default=None)
        if imas_home is None:
            raise ValueError(
                "Legacy URI passed with user=public but $IMAS_HOME is not set"
            )
        path = Path(imas_home) / "shared" / "imasdb" / database / version
    elif user.startswith("/"):
        path = Path(user) / database / version
    else:
        path = Path.home() / "public" / "imasdb" / database / version
    return path / shot / run


def _get_path(uri: URI) -> Path:
    """
    Return the path to the data for a given IMAS URI

    @param uri: a valid IMAS URI
    @return: the path of the IDS data for the given IMAS URI
    """
    path = uri.query.get("path", default=None)
    if path is None:
        path = _get_path_for_legacy_uri(uri)
    else:
        path = Path(path)
    if not path.exists():
        raise ValueError(f"URI path {path} does not exist")
    return path


def imas_files(uri: URI) -> List[Path]:
    """
    Return all the files associated with the given IMAS URI.

    @param uri: a valid IMAS URI
    @return: a list of files which contains the IDS data for the backend specified in the URI
    """
    backend = uri.path
    path = _get_path(uri)
    if backend == "hdf5":
        return list(p.absolute() for p in path.glob("*.h5"))
    elif backend == "mdsplus":
        return [
            path / "ids_001.characteristics",
            path / "ids_001.datafile",
            path / "ids_001.tree",
        ]
    elif backend == "ascii":
        return list(p.absolute() for p in path.glob("*.ids"))
    else:
        raise ValueError(f"Unknown IMAS backend {backend}")


def convert_uri(uri: URI, config: Config) -> None:
    """
    Converts a local IMAS URI to a remote access IMAS URI based on the server.imas_remote_host configuration option.

    Translate locale IMAS URI (imas:<backend>?path=<path>) or legacy IMAS URI
    (imas:<backend>?user=<user>&database=<database>&shot=<shot>&run=<run>&version=<version>) to remote access URI
    (imas://<imas_remote_host>:<imas_remote_port>/uda?path=<path>&backend=<backend>)

    @param uri: The URI to convert
    @param config: Config to read the server.imas_remote_host and server.imas_remote_port options from
    """
    host = config.get_option("server.imas_remote_host", default=None)
    if host is None:
        raise ValueError(
            "Cannot process IMAS data as server.imas_remote_host configuration option not set"
        )
    port = config.get_option("server.imas_remote_port", default=None)
    uri.authority = Authority(host, port, None)
    uri.query.set("backend", uri.path)
    uri.path = Path("uda")
    if uri.query.get("path", default=None) is None:
        path = _get_path_for_legacy_uri(uri)
        uri.query.set("path", str(path))
