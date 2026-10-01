from pathlib import Path

from simdb.imas.utils import SimDBUrl, imas_files

# Tests for simdb.imas.utils.imas_files.
#
# The checksum is computed by feeding the files into a single running hash
# in the order imas_files returns them, so that order must be deterministic
# and identical across platforms. Path.glob() does not sort, so imas_files
# sorts explicitly by file name. See utils.imas_files / imas.checksum.checksum.


def _make_files(directory, names):
    # Create files in an order that does not match the expected sorted order
    for name in names:
        (Path(directory) / name).write_bytes(b"")


def test_hdf5_files_sorted_by_name(tmp_path):
    names = [
        "equilibrium.h5",
        "core_profiles.h5",
        "master.h5",
        "summary.h5",
    ]
    _make_files(tmp_path, names)
    uri = SimDBUrl(f"imas:hdf5?path={tmp_path}")
    result = [p.name for p in imas_files(uri)]
    assert result == sorted(names)


def test_ascii_files_sorted_by_name(tmp_path):
    names = ["equilibrium.ids", "core_profiles.ids", "summary.ids"]
    _make_files(tmp_path, names)
    uri = SimDBUrl(f"imas:ascii?path={tmp_path}")
    result = [p.name for p in imas_files(uri)]
    assert result == sorted(names)


def test_hdf5_files_returns_absolute_paths(tmp_path):
    _make_files(tmp_path, ["core_profiles.h5"])
    uri = SimDBUrl(f"imas:hdf5?path={tmp_path}")
    result = imas_files(uri)
    assert all(p.is_absolute() for p in result)
