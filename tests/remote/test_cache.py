from unittest import mock

from cachelib import FileSystemCache

from simdb.remote.core import cache as cache_module


def test_worker_empties_a_file_system_cache_shared_with_the_api(tmp_path):
    """A worker reaches the API's cache through the directory they share."""
    shared = FileSystemCache(str(tmp_path))
    shared.set("simulation", "stale")
    options = {"CACHE_TYPE": "FileSystemCache", "CACHE_DIR": str(tmp_path)}

    with mock.patch.dict(cache_module.cache_options, options, clear=True):
        cache_module.clear_cache_from_worker()

    assert shared.get("simulation") is None


def test_worker_tolerates_a_missing_cache_directory(tmp_path):
    options = {"CACHE_TYPE": "filesystem", "CACHE_DIR": str(tmp_path / "gone")}

    with mock.patch.dict(cache_module.cache_options, options, clear=True):
        cache_module.clear_cache_from_worker()


def test_worker_leaves_an_in_process_cache_alone(tmp_path):
    """A SimpleCache cannot be reached from another process, so nothing is
    touched: in particular not a directory that happens to be configured."""
    marker = tmp_path / "keep.txt"
    marker.write_text("not a cache file")
    options = {"CACHE_TYPE": "SimpleCache", "CACHE_DIR": str(tmp_path)}

    with mock.patch.dict(cache_module.cache_options, options, clear=True):
        cache_module.clear_cache_from_worker()

    assert marker.read_text() == "not a cache file"
