from pathlib import Path

import pytest

from simdb.cli.manifest import DataType, InvalidManifestError, Manifest


def test_valid_manifest_loading_and_validation(tmp_path):
    # Setup some dummy input/output files to satisfy the file globbing check
    input_file = tmp_path / "input.json"
    input_file.write_text("{}")
    output_file = tmp_path / "output.json"
    output_file.write_text("{}")

    manifest_yaml = f"""\
manifest_version: 2
alias: test-simulation-alias
responsible_name: "John Doe"
inputs:
  - uri: file://{input_file.as_posix()}
  - uri: imas:///user?shot=10000&run=0&database=west
outputs:
  - uri: file://{output_file.as_posix()}
  - uri: imas:///user?shot=10000&run=1&database=west
metadata:
  - machine: ITER
  - code:
      name: METIS
  - description: sample description
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    manifest = Manifest.load_from_file(manifest_file)

    assert manifest.manifest_version == 2
    assert manifest.version == 2
    assert manifest.alias == "test-simulation-alias"
    assert manifest.responsible_name == "John Doe"

    inputs = list(manifest.inputs)
    assert len(inputs) == 2
    assert inputs[0].type == DataType.FILE
    assert inputs[1].type == DataType.IMAS

    outputs = list(manifest.outputs)
    assert len(outputs) == 2
    assert outputs[0].type == DataType.FILE
    assert outputs[1].type == DataType.IMAS


def test_manifest_path_expansion_with_manifest_dir(tmp_path):
    # Setup some dummy file
    input_file = tmp_path / "test_input.json"
    input_file.write_text("{}")

    manifest_yaml = """\
manifest_version: 2
inputs:
  - uri: file:///$MANIFEST_DIR/test_input.json
outputs:
  - uri: imas:///user?shot=10000&run=1&database=west
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    manifest = Manifest.load_from_file(manifest_file)

    inputs = list(manifest.inputs)
    assert len(inputs) == 1
    assert inputs[0].uri.path is not None
    assert Path(inputs[0].uri.path) == input_file


def test_version_1_manifest_is_converted_to_version_2(tmp_path):
    # Version 1 manifests are upgraded to version 2 with a deprecation warning.
    manifest_yaml = """\
manifest_version: 1
alias: legacy-alias
inputs: []
outputs: []
metadata:
  - values:
      machine: ITER
      code: METIS
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.warns(DeprecationWarning, match="version 1 is deprecated"):
        manifest = Manifest.load_from_file(manifest_file)

    assert manifest.manifest_version == 2
    assert manifest.alias == "legacy-alias"
    # v1 "values" metadata is flattened into v2 name/value pairs.
    assert manifest.metadata == {"machine": "ITER", "code": "METIS"}


def test_unknown_manifest_version_is_rejected(tmp_path):
    # Only versions 1 (converted) and 2 are supported.
    manifest_yaml = """\
manifest_version: 3
inputs: []
outputs: []
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError, match="Input should be 2"):
        Manifest.load_from_file(manifest_file)


def test_manifest_version_must_be_integer(tmp_path):
    manifest_yaml = """\
manifest_version: "2"
inputs: []
outputs: []
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError, match="Input should be 2"):
        Manifest.load_from_file(manifest_file)


def test_unknown_section(tmp_path):
    manifest_yaml = """\
manifest_version: 2
inputs: []
outputs: []
unknown_field: true
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError, match="Extra inputs are not permitted"):
        Manifest.load_from_file(manifest_file)


def test_invalid_alias_characters(tmp_path):
    manifest_yaml = """\
manifest_version: 2
alias: "invalid alias"
inputs: []
outputs: []
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError, match="illegal characters in alias"):
        Manifest.load_from_file(manifest_file)


def test_duplicate_uris_in_inputs(tmp_path):
    manifest_yaml = """\
manifest_version: 2
inputs:
  - uri: imas:///user?shot=10000&run=0&database=west
  - uri: imas:///user?shot=10000&run=0&database=west
outputs: []
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError, match="Duplicate URI found in inputs"):
        Manifest.load_from_file(manifest_file)


def test_invalid_metadata_forbidden_characters(tmp_path):
    manifest_yaml = """\
manifest_version: 2
inputs: []
outputs: []
metadata:
  - "machine:name": "value"
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError, match="contains forbidden character"):
        Manifest.load_from_file(manifest_file)


def test_missing_files_causes_validation_error(tmp_path):
    manifest_yaml = """\
manifest_version: 2
inputs:
  - uri: file:///nonexistent_file_path_xyz.json
outputs: []
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError, match="No files found matching path"):
        Manifest.load_from_file(manifest_file)


def test_yaml_syntax_error_reports_line_and_reason(tmp_path):
    manifest_yaml = """\
manifest_version: 2
inputs: []
 outputs: []
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError) as excinfo:
        Manifest.load_from_file(manifest_file)

    [error] = excinfo.value.errors
    assert (error.line, error.column) == (3, 2)
    assert "expected <block end>" in error.message
    assert f"{manifest_file}:3:2: expected <block end>" in str(excinfo.value)


def test_validation_errors_report_location_and_line(tmp_path):
    manifest_yaml = """\
manifest_version: 2
inputs:
  - uri: imas:///user?shot=10000&run=0&database=west
  - path: /some/file
outputs:
  - uri: foo:///bar
metadata:
  - machine: ITER
  - "machine:name": value
unknown_field: true
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError) as excinfo:
        Manifest.load_from_file(manifest_file)

    errors = [(e.line, e.column, e.location, e.message) for e in excinfo.value.errors]
    assert errors == [
        # A missing field is reported at its parent item.
        (4, 5, ("inputs", 1, "uri"), "Field required"),
        (4, 5, ("inputs", 1, "path"), "Extra inputs are not permitted"),
        (6, 5, ("outputs", 0, "uri"), "URL scheme should be 'file' or 'imas'"),
        (
            9,
            5,
            ("metadata", 1),
            "invalid metadata field name machine:name - "
            "contains forbidden character(s): :",
        ),
        (10, 1, ("unknown_field",), "Extra inputs are not permitted"),
    ]
    assert f"{manifest_file}:6:5: outputs[0].uri: URL scheme" in str(excinfo.value)


def test_overridden_values_are_not_reported_at_file_lines(tmp_path):
    manifest_yaml = """\
manifest_version: 2
alias: valid-alias
inputs: []
outputs: []
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError) as excinfo:
        Manifest.load_from_file(manifest_file, overrides={"alias": "invalid alias"})

    [error] = excinfo.value.errors
    assert error.location == ("alias",)
    assert error.line is None
    assert error.message.endswith("(overridden value, not from the file)")


@pytest.mark.parametrize("content", ["", "- a\n- b\n", "just a string\n"])
def test_non_mapping_manifest_is_reported(tmp_path, content):
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(content)

    with pytest.raises(InvalidManifestError) as excinfo:
        Manifest.load_from_file(manifest_file)

    [error] = excinfo.value.errors
    assert "instance of Manifest" not in error.message
    assert error.message.startswith("manifest ")


@pytest.mark.parametrize(
    "value, message",
    [
        ("!ndarray {dtype: float}", "!ndarray requires a 'data' entry"),
        ("!ndarray {data: [1], dtype: nope}", "invalid !ndarray: data type 'nope'"),
    ],
)
def test_invalid_ndarray_reports_line_and_reason(tmp_path, value, message):
    manifest_yaml = f"""\
manifest_version: 2
metadata:
  - x: {value}
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError) as excinfo:
        Manifest.load_from_file(manifest_file)

    [error] = excinfo.value.errors
    assert (error.line, error.column) == (3, 8)
    assert error.message.startswith(message)


def test_version_1_errors_point_at_the_file_as_written(tmp_path):
    manifest_yaml = """\
manifest_version: 1
alias: x y
outputs:
  - uri: foo:///bar
metadata:
  - values:
      ok: 1
      "a:b": 1
  - values: 5
bogus: 2
"""
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(manifest_yaml)

    with pytest.raises(InvalidManifestError) as excinfo, pytest.warns(
        DeprecationWarning
    ):
        Manifest.load_from_file(manifest_file)

    errors = [(e.line, e.location, e.message) for e in excinfo.value.errors]
    assert errors == [
        (2, ("alias",), "illegal characters in alias: x y"),
        (4, ("outputs", 0, "uri"), "URL scheme should be 'file' or 'imas'"),
        (
            6,
            ("metadata", 0, "values"),
            "invalid metadata field name a:b - contains forbidden character(s): :",
        ),
        (9, ("metadata", 1, "values"), "Input should be a valid dictionary"),
        (10, ("bogus",), "Extra inputs are not permitted"),
    ]
