import os
from pathlib import Path
from typing import Collection, Optional

from werkzeug.utils import secure_filename


def secure_path(
    path: Path, common_root: Optional[Path], staging_dir: Path, is_file=True
) -> Path:
    if common_root is None:
        directory = staging_dir
    else:
        directory = staging_dir / path.parent.relative_to(common_root)
    if is_file:
        return directory / secure_filename(path.name)
    else:
        return directory


def find_common_root(paths: Collection[Path]) -> Optional[Path]:
    common_root = Path(os.path.commonpath(paths)) if len(paths) > 1 else None
    return common_root
