import hashlib
import struct
import multiprocessing as mp
from uri import URI
from typing import cast

from .utils import open_imas, list_idss


IGNORED_FIELDS = ('data_dictionary', 'access_layer', 'access_layer_language')


class Hash:
    def digest(self) -> bytes:
        pass

    def update(self, data: bytes):
        pass


def walk_imas(imas_obj, check: Hash) -> None:
    from imas import imasdef
    import numpy as np

    for name in (i for i in dir(imas_obj) if not i.startswith('_')):
        if name in IGNORED_FIELDS:
            continue
        attr = getattr(imas_obj, name)
        if 'numpy.ndarray' in str(type(attr)):
            if attr.size != 0:
                if attr.dtype == np.int32:
                    attr[np.isnan(attr)] = imasdef.EMPTY_INT
                elif attr.dtype == np.float32:
                    attr[np.isnan(attr)] = imasdef.EMPTY_FLOAT
                elif attr.dtype == np.float64:
                    attr[np.isnan(attr)] = imasdef.EMPTY_DOUBLE
                check.update(attr.tobytes())
        elif type(attr) == int:
            if attr != -999999999:
                check.update(struct.pack("<l", attr))
        elif type(attr) == str:
            if attr:
                check.update(attr.encode())
        elif type(attr) == float:
            if attr != -9e+40:
                check.update(struct.pack("f", attr))
        elif '__structure' in str(type(attr)):
            walk_imas(attr, check)
        elif '__structArray' in str(type(attr)):
            for el in attr:
                walk_imas(el, check)


def ids_checksum(ids) -> Hash:
    check = cast(Hash, hashlib.sha256())
    walk_imas(ids, check)
    return check


def _checksum(q: mp.Queue, uri: URI) -> str:
    entry = open_imas(uri)
    idss = list_idss(entry)
    check = hashlib.sha256()
    for name in idss:
        ids = entry.get(name)
        ids_sum = ids_checksum(ids).digest()
        print(f'Checksumming {name} = {ids_sum}')
        check.update(ids_sum)
    entry.close()
    q.put(check.hexdigest())


def checksum(uri: URI) -> str:
    if uri.scheme != "imas":
        raise ValueError("invalid scheme for imas checksum: %s" % uri.scheme)
    q = mp.Queue()
    p = mp.Process(target=_checksum, args=(q, uri))
    p.start()
    check = q.get()
    p.join()
    return check
