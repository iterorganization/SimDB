import hashlib
from pathlib import Path

from simdb.uri import URI

from .utils import imas_files, list_idss, open_imas

IGNORED_FIELDS = ("data_dictionary", "access_layer", "access_layer_language")


class Hash:
    def digest(self) -> bytes:
        pass

    def update(self, data: bytes):
        pass


def checksum(uri: URI, ids_list: list) -> str:
    if uri.scheme != "imas":
        raise ValueError(f"invalid scheme for imas checksum: {uri.scheme}")

    sha1 = hashlib.sha1()

    if not ids_list:
        entry = open_imas(uri)
        ids_list = list_idss(entry)
        entry.close()

    for path in imas_files(uri):
        with path.open("rb") as file:
            ids_name = Path(path).name.split(".")
            if ids_name[1] == "h5" and (
                ids_name[0] != "master"
                and ids_list is not None
                and ids_name[0] not in ids_list
            ):
                continue
            for chunk in iter(lambda: file.read(4096), b""):
                sha1.update(chunk)
    return sha1.hexdigest()
