import hashlib
from pathlib import Path
from typing import Callable, Optional

from simdb.imas.utils import SimDBUrl

#: Algorithm used for all catalog checksums.
CHECKSUM_ALGORITHM = "sha1"
#: Buffer size for reading files while hashing. Larger reads mean far fewer
#: syscalls on big files, which noticeably speeds up checksumming.
READ_CHUNK_SIZE = 1024 * 1024
#: Separates the algorithm from the hex digest in a stored checksum.
CHECKSUM_PREFIX_SEPARATOR = ":"


def hash_file(
    path: Path,
    algorithm: str = CHECKSUM_ALGORITHM,
    progress: Optional[Callable[[int], None]] = None,
) -> str:
    """Return the hex digest of ``path`` computed with ``algorithm``.

    @param progress: optional callback invoked with the number of bytes read for
                     each block, suitable for advancing a progress bar.
    """
    digest = hashlib.new(algorithm)
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(READ_CHUNK_SIZE), b""):
            digest.update(chunk)
            if progress is not None:
                progress(len(chunk))
    return digest.hexdigest()


def format_checksum(hexdigest: str, algorithm: str = CHECKSUM_ALGORITHM) -> str:
    """Prefix a raw hex digest with its algorithm, e.g. ``sha1:2fd4e1c6...``.

    Stored checksums use this ``<algorithm>:<hexdigest>`` form so the encoding
    is self-describing.

    :param hexdigest: the hex representation of the digest
    :param algorithm: the algorithm that produced the digest
    :return: the algorithm-prefixed checksum string
    """
    return f"{algorithm}{CHECKSUM_PREFIX_SEPARATOR}{hexdigest}"


def has_algorithm_prefix(checksum: str) -> bool:
    """Return whether a checksum already carries an ``<algorithm>:`` prefix."""
    return bool(checksum) and CHECKSUM_PREFIX_SEPARATOR in checksum


def strip_checksum(checksum: str) -> str:
    """Return the bare hex digest, dropping any ``<algorithm>:`` prefix.

    Legacy (pre-prefix) checksums are returned unchanged. Used to serialize
    checksums on the wire for API versions that predate the prefix.
    """
    if not has_algorithm_prefix(checksum):
        return checksum
    return checksum.split(CHECKSUM_PREFIX_SEPARATOR, 1)[1]


def checksums_match(a: str, b: str) -> bool:
    """Compare two checksums ignoring any algorithm prefix on either side.

    This keeps validation working across the prefix change: a legacy bare-hex
    checksum (e.g. from an older client) is considered equal to its prefixed
    form (``sha1:<hex>``).
    """
    return strip_checksum(a) == strip_checksum(b)


def file_checksum(uri: SimDBUrl, algorithm: str = CHECKSUM_ALGORITHM) -> str:
    """Generate a checksum for the file at ``uri``.

    Checksums use :data:`CHECKSUM_ALGORITHM` (SHA-1).

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

    return format_checksum(hash_file(path, algorithm), algorithm)
