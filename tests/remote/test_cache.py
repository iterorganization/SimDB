from cachelib import FileSystemCache
from flask_caching.backends.base import BaseCache

from simdb.config import Config
from simdb.remote.core.cache_backend import clear_api_cache_from_worker


class RecordingCache(BaseCache):
    """Stands in for a server-backed cache such as Redis: Flask-Caching
    accepts any dotted path to a backend class."""

    instances = 0
    cleared = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        RecordingCache.instances += 1

    def clear(self) -> bool:
        RecordingCache.cleared += 1
        return True


class BrokenCache(BaseCache):
    """A server-backed cache whose server is down."""

    def clear(self) -> bool:
        raise ConnectionError("cache server unreachable")


def _config(**options) -> Config:
    config = Config()
    for key, value in options.items():
        config.set_option(f"cache.{key}", value)
    return config


def test_worker_empties_a_file_system_cache_shared_with_the_api(tmp_path):
    """A worker reaches the API's cache through the directory they share."""
    shared = FileSystemCache(str(tmp_path))
    shared.set("simulation", "stale")

    clear_api_cache_from_worker(_config(type="FileSystemCache", dir=str(tmp_path)))

    assert shared.get("simulation") is None


def test_worker_empties_any_shared_backend_and_keeps_the_handle():
    """A server-backed cache is built once from the same configuration as the
    API's and emptied on every call."""
    RecordingCache.instances = RecordingCache.cleared = 0
    config = _config(type=f"{__name__}.RecordingCache", key_prefix="unique-1")

    clear_api_cache_from_worker(config)
    clear_api_cache_from_worker(config)

    assert RecordingCache.cleared == 2
    assert RecordingCache.instances == 1


def test_worker_tolerates_a_missing_cache_directory(tmp_path):
    clear_api_cache_from_worker(_config(type="filesystem", dir=str(tmp_path / "gone")))


def test_worker_tolerates_an_unreachable_cache(caplog):
    """The worker's own work is committed by then, so an unreachable cache
    only costs a warning."""
    with caplog.at_level("WARNING"):
        clear_api_cache_from_worker(_config(type=f"{__name__}.BrokenCache"))

    assert "Could not empty the API cache" in caplog.text


def test_worker_leaves_an_in_process_cache_alone(tmp_path):
    """A SimpleCache cannot be reached from another process, so nothing is
    touched: in particular not a directory that happens to be configured."""
    marker = tmp_path / "keep.txt"
    marker.write_text("not a cache file")

    clear_api_cache_from_worker(_config(type="SimpleCache", dir=str(tmp_path)))

    assert marker.read_text() == "not a cache file"


def test_worker_without_a_cache_section_does_nothing():
    clear_api_cache_from_worker(Config())
