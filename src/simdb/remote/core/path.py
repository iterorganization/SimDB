import os
from pathlib import Path
from typing import Collection, Optional

from werkzeug.utils import secure_filename


class UnsafePathError(ValueError):
    """Raised for an uploaded path that would be staged outside the staging dir."""


def _staged_relative(path: Path, common_root: Path) -> Path:
    """
    Return *path* relative to *common_root*, as a path that stays inside it.

    Path.relative_to is purely lexical and keeps ".." segments, so "/data/../etc"
    relative to "/data" is "../etc", which would stage the file outside the staging
    directory entirely. The paths come from the uploaded simulation, and neither
    they nor the common root derived from them are to be trusted.
    """
    try:
        relative = path.relative_to(common_root)
    except ValueError as err:
        raise UnsafePathError(f"path {path} is not below {common_root}") from err

    # normpath resolves the ".." segments that do stay inside, so that a path
    # written as "run/../run" stages next to the one written as "run".
    normalised = Path(os.path.normpath(relative))
    if normalised.is_absolute() or ".." in normalised.parts:
        raise UnsafePathError(f"path {path} escapes {common_root}")
    return normalised


def secure_path(
    path: Path, common_root: Optional[Path], staging_dir: Path, is_file=True
) -> Path:
    """
    Return the location under *staging_dir* that *path* is uploaded to.

    Directories keep their name so that the directory form agrees with the file
    form: the parent of a staged file is the staged form of its directory.

    :param path: the path on the client, from the simulation being uploaded.
    :param common_root: the root the uploaded paths share, or None if they share
        none, in which case everything is flattened into *staging_dir*.
    :param staging_dir: the directory the simulation is staged in.
    :param is_file: True if *path* is a file, False if it is a directory.
    :raises UnsafePathError: if *path* would be staged outside *staging_dir*.
    """
    if not is_file:
        if common_root is None:
            return staging_dir
        return staging_dir / _staged_relative(path, common_root)

    # secure_filename() empties a name that is entirely unusable, such as "..",
    # which would otherwise hand back the directory holding the file.
    name = secure_filename(path.name)
    if not name:
        raise UnsafePathError(f"path {path} has no usable file name")
    if common_root is None:
        return staging_dir / name
    return staging_dir / _staged_relative(path.parent, common_root) / name


def find_common_root(paths: Collection[Path]) -> Optional[Path]:
    common_root = Path(os.path.commonpath(paths)) if len(paths) > 1 else None
    return common_root
