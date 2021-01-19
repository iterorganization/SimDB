import uri as urilib
import os


def sha1_checksum(uri: urilib.URI) -> str:
    """Generate a SHA1 checksum from the given file.

    :param uri: the uri of the file to checksum
    :return: a string containing the hex representation of the computed SHA1 checksum
    """
    import hashlib

    if not uri.scheme.name == "file":
        raise ValueError("Path object must have uri beginning with file:///")
    if not os.path.exists(uri.path):
        raise ValueError('File does not exist')
    if not os.path.isfile(uri.path):
        raise ValueError('File appears to be a directory')

    sha1 = hashlib.sha1()
    with open(uri.path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha1.update(chunk)
    return sha1.hexdigest()
