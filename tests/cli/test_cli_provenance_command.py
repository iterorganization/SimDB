"""Tests for ``simdb provenance``."""

import yaml


def test_provenance_writes_a_yaml_description_of_the_system(invoke, tmp_path):
    provenance_file = tmp_path / "provenance.yaml"

    result = invoke("provenance", str(provenance_file))

    assert result.exit_code == 0
    assert str(provenance_file) in result.output

    provenance = yaml.safe_load(provenance_file.read_text())
    assert set(provenance) == {"environment", "platform"}
    assert provenance["platform"]["system"]
    assert provenance["platform"]["python_version"]


def test_path_like_environment_variables_are_split_into_lists(
    invoke, tmp_path, monkeypatch
):
    monkeypatch.setenv("SIMDB_TEST_PATH", "/first:/second")
    provenance_file = tmp_path / "provenance.yaml"

    assert invoke("provenance", str(provenance_file)).exit_code == 0

    environment = yaml.safe_load(provenance_file.read_text())["environment"]
    assert environment["SIMDB_TEST_PATH"] == ["/first", "/second"]


def test_other_environment_variables_are_kept_as_strings(invoke, tmp_path, monkeypatch):
    monkeypatch.setenv("SIMDB_TEST_VALUE", "plain")
    provenance_file = tmp_path / "provenance.yaml"

    assert invoke("provenance", str(provenance_file)).exit_code == 0

    environment = yaml.safe_load(provenance_file.read_text())["environment"]
    assert environment["SIMDB_TEST_VALUE"] == "plain"


def test_the_file_is_overwritten_on_a_second_run(invoke, tmp_path):
    provenance_file = tmp_path / "provenance.yaml"
    provenance_file.write_text("stale: true\n")

    assert invoke("provenance", str(provenance_file)).exit_code == 0

    assert "stale" not in provenance_file.read_text()
