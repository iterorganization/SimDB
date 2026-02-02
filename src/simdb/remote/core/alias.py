from pathlib import Path

from simdb.remote.core.typing import current_app


def create_alias_dir(simulation):
    base_dir = Path(current_app.simdb_config.get_option("server.upload_folder"))

    # Make sure the aliases directory exists
    (base_dir / "aliases").mkdir(exist_ok=True, parents=True)

    alias_subpath = Path(simulation.alias)
    alias_path = (base_dir / "aliases" / alias_subpath)
    if not alias_path.exists():
        if alias_subpath.parts > 1:
            alias_path.parent.mkdir(parents=True, exist_ok=True)

        alias_path.symlink_to(base_dir / simulation.uuid.hex)
