from pathlib import Path


def sha1_checksum(path: Path) -> str:
    """Generate a SHA1 checksum from the given file.

    :param path: the path of the file to checksum
    :return: a string containing the hex representation of the computed SHA1 checksum
    """
    import hashlib

    if not path.exists():
        raise ValueError('File does not exist')
    if not path.is_file():
        raise ValueError('File appears to be a directory')

    sha1 = hashlib.sha1()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha1.update(chunk)
    return sha1.hexdigest()
