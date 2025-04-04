import os
from typing import List, Any
from datetime import datetime
from pathlib import Path
from dateutil import parser

from ..uri import URI
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
    def partial_get(self, ids: str, path: str, occurrence = 0) -> Any:
        ...

    def list_all_occurrences(self, ids: str) -> List[int]:
        """
        List all occurrences of the given IDS in the IMAS data entry.

        @param
        ids: the IDS name
        @param path: the path to the data
        @return: the list of occurrences
        """
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
            occurrence = entry.list_all_occurrences(name.value)        
            if len(occurrence[0]) > 1:
                for i in range(len(occurrence[0])):
                    if i > 0:
                        idss.append(name.value + "_" + str(i))
            idss.append(name.value)
    return idss


def check_time(entry: DBEntry, ids: str, occurrence) -> None:
    """
    Check the validity of the ids_properties/homogeneous_time field of the given IDS.

    @param entry: the open IMAS data entry
    @param ids: the
    @return:
    """
    from imas import imasdef

    homo_time = entry.partial_get(ids, "ids_properties/homogeneous_time", occurrence)
    if homo_time == imasdef.IDS_TIME_MODE_HOMOGENEOUS:
        time = entry.partial_get(ids, "time", occurrence)
        if time is None or time.size == 0:
            raise ValueError(
                f"IDS {ids} has homogeneous_time flag set to IDS_TIME_MODE_HOMOGENEOUS but invalid time entry."
            )


def _is_al5() -> bool:
    import semantic_version

    al_env = os.environ.get("AL_VERSION", default=None)
    ual_env = os.environ.get("UAL_VERSION", default="5.0.0")
    version = (
        semantic_version.Version(al_env)
        if al_env is not None
        else semantic_version.Version(ual_env)
    )
    return version >= semantic_version.Version("5.0.0")


def _open_legacy(uri: URI) -> DBEntry:
    import imas

    path = uri.query.get("path", default=None)
    if path is not None:
        raise ImasError(f"cannot open AL5 URI {uri} with AL4")

    backend_ids = {
        "hdf5": imas.imasdef.HDF5_BACKEND,
    }

    backend = uri.query.get("backend", default=None)
    user = uri.query.get("user", default=None)
    database = uri.query.get("database", default=None)
    version = uri.query.get("version", default="3")
    shot = uri.query.get("shot", default=None)
    run = uri.query.get("run", default=None)

    if backend not in backend_ids:
        raise ImasError(
            f"backend {backend} is not supported for legacy IMAS, please use AL5"
        )

    backend_id = backend_ids[backend]

    if user is not None:
        entry = imas.DBEntry(
            backend_id,
            database,
            int(shot),
            int(run),
            user_name=user,
            data_version=version,
        )
    else:
        entry = imas.DBEntry(
            backend_id, database, int(shot), int(run), data_version=version
        )

    (status, _) = entry.open()
    if status != 0:
        raise ImasError(f"failed to open IMAS data with URI {uri}")

    return entry


def open_imas(uri: URI) -> DBEntry:
    """
    Open an IMAS URI and return the IMAS entry object.

    @param uri: the IMAS URI to open
    @return: the IMAS data entry object
    """
    import imas

    if uri.scheme != "imas":
        raise ValueError(f"invalid imas URI: {uri} - invalid scheme")

    if uri.query is None:
        raise ValueError(f"invalid imas URI: {uri} - no query found in URI")

    if not _is_al5():
        return _open_legacy(uri)

    path = uri.query.get("path", default=None)
    if path is None:
        path = get_path_for_legacy_uri(uri)
        backend = uri.query.get("backend", default="mdsplus")
        uri = f"imas:{backend}?path={path}"

    entry = imas.DBEntry(str(uri), "r")

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
        try:
            timestamp = parser.parse(creation)
        except parser.ParserError:
            raise ValueError(f"invalid IMAS creation time {creation}")
    else:
        timestamp = datetime.now()
    entry.close()
    return timestamp


def get_path_for_legacy_uri(uri: URI) -> Path:
    user = uri.query.get("user", default=None)
    database = uri.query.get("database", default=None)
    version = uri.query.get("version", default="3")
    shot = uri.query.get("shot", default=None)
    run = uri.query.get("run", default=None)
    backend = uri.query.get("backend", default="hdf5")
    if any(x is None for x in [database, shot, run]):
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
    elif user is not None:
        path = Path(f"~{user}").expanduser() / "public" / "imasdb" / database / version
    else:
        path = Path.home() / "public" / "imasdb" / database / version
    if str(backend) == "mdsplus":
        return path
    else:
        return path / shot / run


def _get_path(uri: URI) -> Path:
    """
    Return the path to the data for a given IMAS URI

    @param uri: a valid IMAS URI
    @return: the path of the IDS data for the given IMAS URI
    """
    path = uri.query.get("path", default=None)
    if path is None:
        raise ValueError("Invalid IMAS URI - path not found in query arguments")

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
    backend = str(uri.path)
    if backend.startswith("/"):
        backend = backend[1:]

    path = _get_path(uri)

    if backend == "uda":
        backend = uri.query.get("backend", default=None)
        if backend is None:
            raise ValueError(
                "Invalid IMAS URI - 'backend' query argument not provided for UDA backend"
            )

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


def convert_uri(uri: URI, path: Path, config: Config) -> URI:
    """
    Converts a local IMAS URI to a remote access IMAS URI based on the server.imas_remote_host configuration option.

    Translate locale IMAS URI (imas:<backend>?path=<path>) to remote access URI
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
    backend = uri.path
    if port is None:
        return URI(f"imas://{host}/uda?path={path}&backend={backend}")
    else:
        port = int(port)
        return URI(f"imas://{host}:{port}/uda?path={path}&backend={backend}")
