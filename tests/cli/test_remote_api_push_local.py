from datetime import datetime, timezone
from pathlib import Path

import pytest

from simdb.checksum import hash_file
from simdb.cli.remote_api import (
    APIError,
    _expand_directories,
    _find_partition_for_file,
)
from simdb.remote.models import FileData


def _file_data(uri: str, file_type: str = "FILE") -> FileData:
    return FileData(
        type=file_type,
        uri=uri,
        checksum="stale",
        datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_find_partition_prefers_the_deepest_root():
    """A catch-all partition does not shadow a more specific one."""
    partitions = {"root": "/", "data": "/mnt/data"}

    assert _find_partition_for_file(Path("/mnt/data/run/x.txt"), partitions) == (
        "data",
        Path("run/x.txt"),
    )
    assert _find_partition_for_file(Path("/sdcc/run/x.txt"), partitions) == (
        "root",
        Path("sdcc/run/x.txt"),
    )


def test_find_partition_without_a_match():
    with pytest.raises(APIError, match="configured partitions: data"):
        _find_partition_for_file(Path("/elsewhere/x.txt"), {"data": "/mnt/data"})


def test_expand_directories_rewrites_the_uri_of_a_single_file(tmp_path: Path):
    source = tmp_path / "run" / "x.txt"
    source.parent.mkdir()
    source.write_text("contents")
    file = _file_data(f"file:{source}")

    expanded = _expand_directories([file], {"data": str(tmp_path)})

    assert len(expanded) == 1
    assert expanded[0].uri == "data:run/x.txt"
    assert expanded[0].checksum == hash_file(source)
    # A file that maps onto a single source keeps its identity.
    assert expanded[0].uuid == file.uuid


def test_expand_directories_expands_a_directory(tmp_path: Path):
    directory = tmp_path / "run"
    directory.mkdir()
    for name in ("b.txt", "a.txt"):
        (directory / name).write_text(name)
    file = _file_data(f"file:{directory}")

    expanded = _expand_directories([file], {"data": str(tmp_path)})

    assert [f.uri for f in expanded] == ["data:run/a.txt", "data:run/b.txt"]
    # Each file needs its own identity to be stored on the remote.
    assert len({f.uuid for f in expanded}) == 2


def test_expand_directories_rejects_nested_directories(tmp_path: Path):
    directory = tmp_path / "run"
    (directory / "nested").mkdir(parents=True)
    file = _file_data(f"file:{directory}")

    with pytest.raises(APIError, match="Nested directory found"):
        _expand_directories([file], {"data": str(tmp_path)})


def test_expand_directories_only_lists_the_files_of_an_imas_backend(tmp_path: Path):
    directory = tmp_path / "run"
    directory.mkdir()
    for name in ("master.h5", "equilibrium.h5", "notes.txt"):
        (directory / name).write_text(name)
    file = _file_data(f"imas:hdf5?path={directory}", file_type="IMAS")

    expanded = _expand_directories([file], {"data": str(tmp_path)})

    assert [f.uri for f in expanded] == [
        "data:run/equilibrium.h5",
        "data:run/master.h5",
    ]


def test_expand_directories_reports_an_unusable_imas_uri(tmp_path: Path):
    file = _file_data(f"imas:hdf5?path={tmp_path / 'missing'}", file_type="IMAS")

    with pytest.raises(APIError, match="Failed to list IMAS files"):
        _expand_directories([file], {"data": str(tmp_path)})


def test_expand_directories_without_configured_partitions(tmp_path: Path):
    source = tmp_path / "x.txt"
    source.write_text("contents")

    with pytest.raises(APIError, match="configured partitions: none"):
        _expand_directories([_file_data(f"file:{source}")], {})
