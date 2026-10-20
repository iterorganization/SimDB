import contextlib

from cachelib import FileSystemCache
from flask import request
from flask_caching import Cache

from simdb.config import Config

config = Config("app.cfg")
config.load()
cache_options = {
    "CACHE_" + k.upper(): v for (k, v) in config.get_section("cache", {}).items()
}

cache = Cache(config=cache_options)

_FILE_SYSTEM_CACHE_TYPES = ("filesystem", "FileSystemCache")


def cache_key(*args, **kwargs) -> str:
    headers = []
    for key, value in request.headers.items():
        if "simdb-" in key.lower():
            headers.append(f"{key.lower()}:{value}")
    return request.url + "?" + "&".join(headers)


def clear_cache():
    # If /tmp has been cleared by the system then we should ignore this exception
    with contextlib.suppress(FileNotFoundError):
        cache.clear()


def clear_cache_from_worker() -> None:
    """Empty the API's response cache from outside the API process.

    The Celery workers change simulations behind the API's back: the ingestion
    status, the ingested files and the validation outcome. The responses the
    API has cached for those simulations are stale from then on, so a worker
    calls this after it commits such a change.

    Only a ``FileSystemCache`` can be reached from another process. A
    ``SimpleCache`` lives in the memory of the API process and cannot be
    invalidated from a worker, and a ``NullCache`` stores nothing.
    """
    if cache_options.get("CACHE_TYPE") not in _FILE_SYSTEM_CACHE_TYPES:
        return
    cache_dir = cache_options.get("CACHE_DIR")
    if not cache_dir:
        return
    with contextlib.suppress(FileNotFoundError):
        FileSystemCache(str(cache_dir)).clear()
