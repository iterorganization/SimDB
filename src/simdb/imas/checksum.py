import hashlib
from pathlib import Path

from simdb.checksum import CHECKSUM_ALGORITHM, READ_CHUNK_SIZE
from simdb.imas.utils import SimDBUrl

from .utils import imas_files, list_idss, open_imas

IGNORED_FIELDS = ("data_dictionary", "access_layer", "access_layer_language")


def checksum(uri: SimDBUrl, ids_list: list, algorithm: str = CHECKSUM_ALGORITHM) -> str:
    digest = hashlib.new(algorithm)

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
            for chunk in iter(lambda: file.read(READ_CHUNK_SIZE), b""):
                digest.update(chunk)
    return digest.hexdigest()
