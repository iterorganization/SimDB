def sha1_checksum(path: str) -> str:
    """
    Generate a SHA1 checksum from the given file.

    :param path:
    :return:
    """
    import hashlib

    sha1 = hashlib.sha1()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha1.update(chunk)
    return sha1.hexdigest()
