"""Tests for the staging path helpers shared by ingestion and verification.

The directory form has to agree with the file form: the IMAS files of a
simulation are staged one by one with ``is_file=True``, while both the checksum
verification in ``apis/files.py`` and the URI rewrite in ``apis/v1_2`` resolve
the directory holding them with ``is_file=False``. If the two disagree the
ingested URI points at a directory that was never written.
"""

from pathlib import Path

import pytest

from simdb.imas.utils import SimDBUrl
from simdb.remote.core.path import UnsafePathError, find_common_root, secure_path

STAGING = Path("/staging")


@pytest.mark.parametrize(
    "imas_dir",
    [
        # A name secure_filename leaves alone, and two that it rewrites.
        "/data/sim/1",
        "/data/sim/run 1",
        "/data/sim/résumé",
    ],
)
def test_staged_directory_holds_the_staged_files(imas_dir):
    ids_files = [Path(imas_dir) / f"{name}.h5" for name in ("core_profiles", "master")]
    common_root = find_common_root([Path(imas_dir), Path("/data/input.json")])

    staged_dir = secure_path(Path(imas_dir), common_root, STAGING, is_file=False)

    for ids_file in ids_files:
        staged_file = secure_path(ids_file, common_root, STAGING)
        assert staged_file.parent == staged_dir


def test_without_a_common_root_everything_is_flattened_into_staging():
    staged_dir = secure_path(Path("/data/sim/1"), None, STAGING, is_file=False)
    staged_file = secure_path(Path("/data/sim/1/core_profiles.h5"), None, STAGING)

    assert staged_dir == STAGING
    assert staged_file == STAGING / "core_profiles.h5"


def test_file_names_are_sanitised():
    common_root = Path("/data")

    assert secure_path(Path("/data/sim/my data.h5"), common_root, STAGING) == (
        STAGING / "sim" / "my_data.h5"
    )


@pytest.mark.parametrize(
    "path",
    [
        # The uploaded paths are attacker controlled, and so is the common root
        # derived from them: os.path.commonpath treats ".." as an ordinary segment,
        # so it happily reports "/data" as the root of "/data/../../etc/pwned".
        "/data/../../etc/pwned",
        "/data/sim/../../../etc/pwned",
        "/data/..",
    ],
)
@pytest.mark.parametrize("is_file", [True, False])
def test_paths_that_leave_the_staging_directory_are_refused(path, is_file):
    with pytest.raises(UnsafePathError):
        secure_path(Path(path), Path("/data"), STAGING, is_file=is_file)


def test_a_refused_path_is_a_value_error():
    """The API layers report it as a client error by catching ValueError."""
    assert issubclass(UnsafePathError, ValueError)


def test_paths_outside_the_common_root_are_refused():
    with pytest.raises(UnsafePathError):
        secure_path(Path("/elsewhere/sim/f.h5"), Path("/data"), STAGING)


@pytest.mark.parametrize("name", ["..", "???", "$$$"])
def test_file_names_that_sanitise_to_nothing_are_refused(name):
    """secure_filename() empties these, which would stage the file as its own
    directory -- silently, for the flattened form, and over the top of whatever
    else was flattened into it."""
    with pytest.raises(UnsafePathError):
        secure_path(Path("/data/sim") / name, Path("/data"), STAGING)
    with pytest.raises(UnsafePathError):
        secure_path(Path("/data/sim") / name, None, STAGING)


def test_a_traversal_that_stays_inside_is_normalised():
    common_root = Path("/data")

    staged_dir = secure_path(
        Path("/data/x/../sim"), common_root, STAGING, is_file=False
    )
    staged_file = secure_path(
        Path("/data/x/../sim/core_profiles.h5"), common_root, STAGING
    )

    assert staged_dir == STAGING / "sim"
    assert staged_file == STAGING / "sim" / "core_profiles.h5"
    assert staged_file.parent == staged_dir


def test_file_uri_paths_are_normalised_before_they_reach_staging():
    """Why only the IMAS path needs the guard above at the API layer.

    SimDBUrl is a pydantic AnyUrl, which normalises the *path* component, so a
    "file:" URI cannot carry a traversal into secure_path. The IMAS directory
    travels in the query string instead, which is not normalised -- and neither is
    anything else that reaches the helper by another route, which is why the guard
    lives in the helper rather than at the call sites.
    """
    assert SimDBUrl("file:///data/sim/../../etc/pwned").path == "/etc/pwned"

    imas = SimDBUrl("imas:hdf5?path=/data/sim/../../etc/pwned")
    assert dict(imas.query_params())["path"] == "/data/sim/../../etc/pwned"
