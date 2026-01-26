from simdb.uri import URI, Query


def checksum(uri: URI) -> str:
    if uri.scheme != "uda":
        raise ValueError(f"invalid scheme for UDA checksum: {uri.scheme}")

    import hashlib

    import pyuda

    if uri.query is None:
        raise ValueError(
            "UDA object must have uri uda:///?signal=<SIGNAL>&source=<SOURCE>"
        )

    query: Query = uri.query
    signal = query.get("signal")
    source = query.get("source")
    if signal is None or source is None:
        raise ValueError(
            "UDA object must have uri uda:///?signal=<SIGNAL>&source=<SOURCE>"
        )

    client = pyuda.Client()
    res = client.get(signal, source, raw=True)

    sha1 = hashlib.sha1()
    sha1.update(res)

    return sha1.hexdigest()
