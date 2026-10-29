"""The API's response cache as configured, for code outside a request.

Importing this module has no side effects, unlike :mod:`.cache`, which reads
the server configuration and builds the API's cache when imported.
"""

import contextlib
import functools
import logging
from typing import Any, Dict, Tuple

from flask import Flask
from flask_caching import Cache

from simdb.config import Config

logger = logging.getLogger(__name__)

_IN_PROCESS_CACHE_TYPES = ("null", "NullCache", "simple", "SimpleCache")
"""Cache types that live inside the API process, so no other process can reach them."""


def cache_options_from(config: Config) -> Dict[str, Any]:
    """The ``[cache]`` section of CONFIG as Flask-Caching settings."""
    return {
        "CACHE_" + key.upper(): value
        for key, value in config.get_section("cache", default={}).items()
    }


@functools.lru_cache(maxsize=None)
def _api_cache(options: Tuple[Tuple[str, Any], ...]) -> Tuple[Cache, Flask]:
    """A handle on the API's cache built from OPTIONS, one per process.

    Flask-Caching builds its backends for a Flask app, so a bare one is made
    for it. The handle is kept: a server-backed cache opens a connection pool.
    """
    app = Flask("simdb-worker-cache")
    return Cache(app, with_jinja2_ext=False, config=dict(options)), app


def clear_api_cache_from_worker(config: Config) -> None:
    """Empty the API's response cache from outside the API process.

    The Celery workers change simulations behind the API's back: the ingestion
    status, the ingested files and the validation outcome. The responses the
    API has cached for those simulations are stale from then on, so a worker
    calls this after it commits such a change, with its own loaded CONFIG.

    Any backend shared between processes works: a directory for
    ``FileSystemCache``, a server for ``RedisCache`` or ``MemcachedCache``. A
    ``SimpleCache`` lives in the memory of the API process and cannot be
    invalidated from a worker, and a ``NullCache`` stores nothing, so neither
    is touched.

    Never raises: the worker's own work is committed by the time this runs,
    and an unreachable cache must not turn it into a failed ingestion.
    """
    options = cache_options_from(config)
    if options.get("CACHE_TYPE", "null") in _IN_PROCESS_CACHE_TYPES:
        return
    try:
        api_cache, app = _api_cache(tuple(sorted(options.items())))
        with app.app_context(), contextlib.suppress(FileNotFoundError):
            api_cache.clear()
    except Exception:
        logger.warning(
            "Could not empty the API cache; cached responses may be stale until "
            "they expire",
            exc_info=True,
        )
