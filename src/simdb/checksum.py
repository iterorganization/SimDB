def sha1_checksum(path: str) -> str:
    """Generate a SHA1 checksum from the given file.

    :param path: the path of the file to checksum
    :return: a string containing the hex representation of the computed SHA1 checksum
    """
    import hashlib

    sha1 = hashlib.sha1()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha1.update(chunk)
    return sha1.hexdigest()
