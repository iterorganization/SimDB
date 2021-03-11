from uri import URI


def sha1_checksum(uri: URI) -> str:
    """Generate a SHA1 checksum from the given file.

    :param uri: the URI of the file to checksum
    :return: a string containing the hex representation of the computed SHA1 checksum
    """
    if uri.scheme != "file":
        raise ValueError("invalid scheme for file checksum: %s" % uri.scheme)
    path = uri.path

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
