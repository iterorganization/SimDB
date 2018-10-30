import sys

def checksum(signal: str, source: str) -> str:
    import pyuda
    import hashlib

    print('fetching: %s %s' % (signal, source), file=sys.stderr)

    client = pyuda.Client()
    res = client.get(signal, source, raw=True)

    sha1 = hashlib.sha1()
    sha1.update(res)

    return sha1.hexdigest()
