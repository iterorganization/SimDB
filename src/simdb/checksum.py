import hashlib
from pathlib import Path

from simdb.imas.utils import SimDBUrl


def calculate_checksum(path: Path) -> str:
    """Generate a SHA1 checksum from the file at the given path.

    :param path: the path of the file to checksum
    :return: a string containing the hex representation of the computed SHA1 checksum
    """
    sha1 = hashlib.sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha1.update(chunk)
    return sha1.hexdigest()


def sha1_checksum(uri: SimDBUrl) -> str:
    """Generate a SHA1 checksum from the given file.

    :param uri: the URI of the file to checksum
    :return: a string containing the hex representation of the computed SHA1 checksum
    """
    if uri.scheme != "file":
        raise ValueError(f"invalid scheme for file checksum: {uri.scheme}")
    if uri.path is None:
        raise ValueError("Path is not set")
    path = Path(uri.path)

    if not path.exists():
        raise ValueError("File does not exist")
    if not path.is_file():
        raise ValueError("File appears to be a directory")

    return calculate_checksum(path)
