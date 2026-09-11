from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from simdb.remote.core import alias


def test_nested_alias_uses_relative_symlink_that_survives_move(tmp_path, monkeypatch):
    base_dir = tmp_path / "storage"
    base_dir.mkdir()

    simulation = SimpleNamespace(alias="user/project/case", uuid=uuid4())
    simulation_dir = base_dir / simulation.uuid.hex
    simulation_dir.mkdir()
    config = SimpleNamespace(
        get_string_option=lambda option: str(base_dir),
    )
    monkeypatch.setattr(
        alias,
        "current_app",
        SimpleNamespace(simdb_config=config),
    )

    alias.create_alias_dir(simulation)

    alias_path = base_dir / "aliases" / simulation.alias
    assert alias_path.readlink() == Path("../../..") / simulation.uuid.hex
    assert alias_path.resolve() == simulation_dir

    moved_base_dir = tmp_path / "moved-storage"
    base_dir.rename(moved_base_dir)

    moved_alias_path = moved_base_dir / "aliases" / simulation.alias
    assert moved_alias_path.resolve() == moved_base_dir / simulation.uuid.hex
