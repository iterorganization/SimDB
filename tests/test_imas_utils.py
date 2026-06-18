import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from simdb.imas.utils import imas_files
from simdb.uri import URI


class ImasFilesTests(unittest.TestCase):
    """Tests for simdb.imas.utils.imas_files.

    The checksum is computed by feeding the files into a single running hash
    in the order imas_files returns them, so that order must be deterministic
    and identical across platforms. Path.glob() does not sort, so imas_files
    sorts explicitly by file name. See utils.imas_files / imas.checksum.checksum.
    """

    def _make_files(self, directory, names):
        # Create files in an order that does not match the expected sorted order
        for name in names:
            (Path(directory) / name).write_bytes(b"")

    def test_hdf5_files_sorted_by_name(self):
        names = [
            "equilibrium.h5",
            "core_profiles.h5",
            "master.h5",
            "summary.h5",
        ]
        with TemporaryDirectory() as tmp:
            self._make_files(tmp, names)
            uri = URI(f"imas:hdf5?path={tmp}")
            result = [p.name for p in imas_files(uri)]
            self.assertEqual(result, sorted(names))

    def test_ascii_files_sorted_by_name(self):
        names = ["equilibrium.ids", "core_profiles.ids", "summary.ids"]
        with TemporaryDirectory() as tmp:
            self._make_files(tmp, names)
            uri = URI(f"imas:ascii?path={tmp}")
            result = [p.name for p in imas_files(uri)]
            self.assertEqual(result, sorted(names))

    def test_hdf5_files_returns_absolute_paths(self):
        with TemporaryDirectory() as tmp:
            self._make_files(tmp, ["core_profiles.h5"])
            uri = URI(f"imas:hdf5?path={tmp}")
            result = imas_files(uri)
            self.assertTrue(all(p.is_absolute() for p in result))


if __name__ == "__main__":
    unittest.main()
