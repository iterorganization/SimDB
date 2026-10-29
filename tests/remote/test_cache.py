from cachelib import FileSystemCache

from simdb.config import Config
from simdb.remote.core.cache_backend import clear_api_cache_from_worker


def test_worker_empties_a_file_system_cache_shared_with_the_api(tmp_path):
    """A worker reaches the API's cache through the directory they share."""
    shared = FileSystemCache(str(tmp_path))
    shared.set("simulation", "stale")
    config = Config()
    config.set_option("cache.type", "FileSystemCache")
    config.set_option("cache.dir", str(tmp_path))

    clear_api_cache_from_worker(config)

    assert shared.get("simulation") is None
