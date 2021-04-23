import hashlib
import struct
import multiprocessing as mp
from uri import URI
from typing import cast

from .utils import open_imas, list_idss


class Hash:
    def digest(self) -> bytes:
        pass

    def update(self, data: bytes):
        pass


def walk_imas(imas_obj, check: Hash) -> None:
    for name in (i for i in dir(imas_obj) if not i.startswith('_')):
        attr = getattr(imas_obj, name)
        if 'numpy.ndarray' in str(type(attr)):
            if attr.size != 0:
                check.update(attr.tobytes())
        if type(attr) == int:
            if attr != -999999999:
                check.update(struct.pack("<l", attr))
        if type(attr) == str:
            if attr:
                check.update(attr.encode())
        if type(attr) == float:
            if attr != -9e+40:
                check.update(struct.pack("f", attr))
        elif '__structure' in str(type(attr)):
            walk_imas(attr, check)


def ids_checksum(ids) -> Hash:
    check = cast(Hash, hashlib.sha256())
    walk_imas(ids, check)
    return check


def _checksum(q: mp.Queue, uri: URI) -> str:
    imas_obj = open_imas(uri)
    idss = list_idss(imas_obj)
    check = hashlib.sha256()
    for ids in idss:
        print(f'checksumming {ids}')
        check.update(ids_checksum(ids).digest())
    imas_obj.close()
    q.put(check.hexdigest())
    # return check.hexdigest()


def checksum(uri: URI) -> str:
    if uri.scheme != "imas":
        raise ValueError("invalid scheme for imas checksum: %s" % uri.scheme)
    q = mp.Queue()
    p = mp.Process(target=_checksum, args=(q, uri))
    p.start()
    check = q.get()
    p.join()
    return check
