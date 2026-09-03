import hashlib
from pathlib import Path

from simdb.imas.utils import SimDBUrl

#: Algorithm used to generate checksums. Prepended to every stored checksum as a
#: ``<algorithm>:<hexdigest>`` prefix so the encoding is self-describing.
CHECKSUM_ALGORITHM = "sha1"


def format_checksum(hexdigest: str, algorithm: str = CHECKSUM_ALGORITHM) -> str:
    """Prefix a raw hex digest with its algorithm, e.g. ``sha1:2fd4e1c6...``.

    :param hexdigest: the hex representation of the digest
    :param algorithm: the algorithm that produced the digest
    :return: the algorithm-prefixed checksum string
    """
    return f"{algorithm}:{hexdigest}"


def is_prefixed(checksum: str) -> bool:
    """Return whether a checksum already carries an ``<algorithm>:`` prefix."""
    return bool(checksum) and ":" in checksum


def strip_checksum(checksum: str) -> str:
    """Return the bare hex digest, dropping any ``<algorithm>:`` prefix.

    Legacy (pre-prefix) checksums are returned unchanged. Used to serialize
    checksums on the wire for API versions that predate the prefix.
    """
    if not checksum:
        return checksum
    return checksum.split(":", 1)[1] if ":" in checksum else checksum


def checksums_match(a: str, b: str) -> bool:
    """Compare two checksums ignoring any algorithm prefix on either side.

    This keeps validation working across the prefix change: a legacy bare-hex
    checksum (e.g. from an older client) is considered equal to its prefixed
    form (``sha1:<hex>``).
    """
    return strip_checksum(a) == strip_checksum(b)


def sha1_checksum(uri: SimDBUrl) -> str:
    """Generate a SHA1 checksum from the given file.

    :param uri: the URI of the file to checksum
    :return: the algorithm-prefixed checksum (``sha1:<hexdigest>``)
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

    sha1 = hashlib.sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha1.update(chunk)
    return format_checksum(sha1.hexdigest())
