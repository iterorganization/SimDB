import hashlib
from pathlib import Path
import struct
import multiprocessing as mp
from typing import cast

from .utils import open_imas, list_idss, imas_files
from ..uri import URI


IGNORED_FIELDS = ("data_dictionary", "access_layer", "access_layer_language")


class Hash:
    def digest(self) -> bytes:
        pass

    def update(self, data: bytes):
        pass


# def walk_imas(imas_obj, check: Hash, path="") -> None:
#     from imas import imasdef
#     import numpy as np

#     for name in (i for i in dir(imas_obj) if not i.startswith("_")):
#         if name in IGNORED_FIELDS:
#             continue
#         attr = getattr(imas_obj, name)
#         if "numpy.ndarray" in str(type(attr)):
#             if attr.size != 0:
#                 # if np.isnan(attr).any():
#                 #     print(path, name)
#                 if attr.dtype == np.int32:
#                     attr[np.isnan(attr)] = imasdef.INT_0D
#                 elif attr.dtype == np.float32:
#                     attr[np.isnan(attr)] = imasdef.FLT_0D
#                 elif attr.dtype == np.float64:
#                     attr[np.isnan(attr)] = imasdef.EMPTY_DOUBLE
#                 check.update(attr.tobytes())
#         elif isinstance(attr, int):
#             if attr != imasdef.EMPTY_INT:
#                 check.update(struct.pack("<l", attr))
#         elif isinstance(attr, str):
#             if attr and attr[0] != chr(0):
#                 check.update(attr.encode())
#         elif isinstance(attr, float):
#             if attr != imasdef.EMPTY_FLOAT:
#                 check.update(struct.pack("f", attr))
#         elif "__structure" in str(type(attr)):
#             walk_imas(attr, check, path=f"{path}.{name}")
#         elif "__structArray" in str(type(attr)):
#             for i, el in enumerate(attr):
#                 walk_imas(el, check, path=f"{path}.{name}[{i}]")


# def ids_checksum(ids) -> Hash:
#     check = cast(Hash, hashlib.sha256())
#     walk_imas(ids, check)
#     return check


def _checksum(q: mp.Queue, uri: URI) -> str:
    entry = open_imas(uri)
    idss = list_idss(entry)
    check = hashlib.sha256()
    for name in idss:
        print(f"Checksumming {name}", flush=True)
        ids = entry.get(name)
        check.update(ids_checksum(ids).digest())
    entry.close()
    q.put(check.hexdigest())


def checksum(uri: URI, ids_list: list) -> str:
    if uri.scheme != "imas":
        raise ValueError("invalid scheme for imas checksum: %s" % uri.scheme)

    import hashlib
    sha1 = hashlib.sha1()

    for path in imas_files(uri):
        with open(path, "rb") as file:
            ids_name = Path(path).name.split(".")
            if ids_name[1] == "h5":
                if ids_name[0] != "master" and ids_list is not None and ids_name[0] not in ids_list:
                    continue
            for chunk in iter(lambda: file.read(4096), b""):
                sha1.update(chunk)

    return sha1.hexdigest()
