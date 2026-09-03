import hashlib
from pathlib import Path
from typing import Callable, Optional

from simdb.imas.utils import SimDBUrl

#: Algorithm used for all catalog checksums.
CHECKSUM_ALGORITHM = "sha1"
#: Buffer size for reading files while hashing. Larger reads mean far fewer
#: syscalls on big files, which noticeably speeds up checksumming.
READ_CHUNK_SIZE = 1024 * 1024


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


def file_checksum(uri: SimDBUrl, algorithm: str = CHECKSUM_ALGORITHM) -> str:
    """Generate a checksum for the file at ``uri``.

    Checksums use :data:`CHECKSUM_ALGORITHM` (SHA-1).

    :param uri: the URI of the file to checksum
    :return: a string containing the hex representation of the computed checksum
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

    return hash_file(path, algorithm)
