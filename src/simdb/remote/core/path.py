import os
from pathlib import Path
from typing import Collection, Optional

from werkzeug.utils import secure_filename


def secure_path(
    path: Path, common_root: Optional[Path], staging_dir: Path, is_file=True
) -> Path:
    if common_root is None:
        return staging_dir / secure_filename(path.name) if is_file else staging_dir
    if is_file:
        return (
            staging_dir
            / path.parent.relative_to(common_root)
            / secure_filename(path.name)
        )
    return staging_dir / path.relative_to(common_root)


def find_common_root(paths: Collection[Path]) -> Optional[Path]:
    common_root = Path(os.path.commonpath(paths)) if len(paths) > 1 else None
    return common_root
