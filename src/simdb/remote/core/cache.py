import contextlib

from flask import request
from flask_caching import Cache

from simdb.config import Config

from .cache_backend import cache_options_from

config = Config("app.cfg")
config.load()
cache_options = cache_options_from(config)

cache = Cache(config=cache_options)


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
