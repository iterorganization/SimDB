"""Tests for ``simdb manifest``."""

import yaml

from simdb.cli.manifest import Manifest


def test_check_accepts_a_valid_manifest(invoke, manifest_file):
    result = invoke("manifest", "check", str(manifest_file))

    assert result.exit_code == 0
    assert "ok" in result.output


def test_check_rejects_an_invalid_manifest(invoke, tmp_path):
    manifest_file = tmp_path / "broken.yaml"
    manifest_file.write_text("manifest_version: 2\nalias: 'not a valid alias'\n")

    result = invoke("manifest", "check", str(manifest_file))

    assert result.exit_code != 0
    assert "illegal characters in alias" in str(result.exception)


def test_check_requires_the_file_to_exist(invoke, tmp_path):
    result = invoke("manifest", "check", str(tmp_path / "missing.yaml"))

    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_create_writes_a_manifest_from_the_template(invoke, tmp_path):
    manifest_file = tmp_path / "new-manifest.yaml"

    result = invoke("manifest", "create", str(manifest_file))

    assert result.exit_code == 0
    assert str(manifest_file) in result.output
    assert manifest_file.exists()
    assert yaml.safe_load(manifest_file.read_text())["manifest_version"] == 2


def test_a_created_manifest_carries_the_template_placeholders(invoke, tmp_path):
    """``create`` writes a skeleton, so ``check`` still has something to report.

    The template points at ``/home/user/path/to/a/file1`` and friends, which the
    user is expected to replace; checking it unedited must say so rather than
    pass silently.
    """
    manifest_file = tmp_path / "new-manifest.yaml"
    assert invoke("manifest", "create", str(manifest_file)).exit_code == 0

    result = invoke("manifest", "check", str(manifest_file))

    assert result.exit_code != 0
    assert "No files found matching path" in str(result.exception)


def test_check_loads_the_manifest_it_was_given(invoke, manifest_file):
    """``check`` reports on the requested file, not on a default one."""
    loaded = Manifest.load_from_file(manifest_file)

    assert loaded.alias == "simulation-alias"
    assert len(loaded.inputs) == 1
    assert len(loaded.outputs) == 1
