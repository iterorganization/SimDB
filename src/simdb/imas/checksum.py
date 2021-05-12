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


def walk_imas(imas_obj, check: Hash, path='') -> None:
    from imas import imasdef
    import numpy as np

    for name in (i for i in dir(imas_obj) if not i.startswith('_')):
        if name in IGNORED_FIELDS:
            continue
        attr = getattr(imas_obj, name)
        if 'numpy.ndarray' in str(type(attr)):
            if attr.size != 0:
                #if np.isnan(attr).any():
                #    print(path, name)
                if attr.dtype == np.int32:
                    attr[np.isnan(attr)] = imasdef.EMPTY_INT
                elif attr.dtype == np.float32:
                    attr[np.isnan(attr)] = imasdef.EMPTY_FLOAT
                elif attr.dtype == np.float64:
                    attr[np.isnan(attr)] = imasdef.EMPTY_DOUBLE
                check.update(attr.tobytes())
        elif type(attr) == int:
            if attr != imasdef.EMPTY_INT:
                check.update(struct.pack("<l", attr))
        elif type(attr) == str:
            if attr and attr[0] != chr(0):
                check.update(attr.encode())
        elif type(attr) == float:
            if attr != imasdef.EMPTY_FLOAT:
                check.update(struct.pack("f", attr))
        elif '__structure' in str(type(attr)):
            walk_imas(attr, check, path=f'{path}.{name}')
        elif '__structArray' in str(type(attr)):
            for i, el in enumerate(attr):
                walk_imas(el, check, path=f'{path}.{name}[{i}]')


def ids_checksum(ids) -> Hash:
    check = cast(Hash, hashlib.sha256())
    walk_imas(ids, check)
    return check


def _checksum(q: mp.Queue, uri: URI) -> str:
    entry = open_imas(uri)
    idss = list_idss(entry)
    check = hashlib.sha256()
    for name in idss:
        print(f'Checksumming {name}', flush=True)
        ids = entry.get(name)
        check.update(ids_checksum(ids).digest())
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
