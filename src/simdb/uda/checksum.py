import uri as urilib


def checksum(uri: urilib.URI) -> str:
    import pyuda
    import hashlib

    query: urilib.QSO = uri.query
    signal = query.get('signal')
    source = query.get('source')
    if signal is None or source is None:
        raise ValueError('UDA object must have uri uda:///?signal=<SIGNAL>&source=<SOURCE>')

    client = pyuda.Client()
    res = client.get(signal, source, raw=True)

    sha1 = hashlib.sha1()
    sha1.update(res)

    return sha1.hexdigest()
