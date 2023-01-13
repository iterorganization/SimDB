from werkzeug.utils import secure_filename
from pathlib import Path
from typing import Optional


def secure_path(path: Path, common_root: Optional[Path], staging_dir: Path) -> Path:
    file_name = secure_filename(path.name)
    if common_root is None:
        directory = staging_dir
    else:
        directory = staging_dir / path.parent.relative_to(common_root)
    return directory / file_name
