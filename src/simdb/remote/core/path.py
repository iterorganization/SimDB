from werkzeug.utils import secure_filename
from pathlib import Path


def secure_path(path: Path, common_root: Path, staging_dir: Path) -> Path:
    file_name = secure_filename(path.name)
    directory = staging_dir / path.parent.relative_to(common_root)
    return directory / file_name
