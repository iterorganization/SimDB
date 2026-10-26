from pathlib import Path
from unittest import mock

from simdb.cli.manifest import DataType, Manifest
from simdb.database.models import Simulation
from simdb.enums import IngestionStatus
from simdb.imas.utils import SimDBUrl


def test_create_simulation_without_manifest_creates_empty_sim():
    sim = Simulation(manifest=None)
    assert sim.id is None
    assert sim.uuid is None
    assert sim.alias is None
    assert sim.inputs == []
    assert sim.outputs == []
    assert sim.meta == []


@mock.patch("simdb.cli.manifest.DataObject")
@mock.patch("simdb.cli.manifest.Manifest")
def test_create_simulation_with_manifest(manifest_cls, data_object_cls):
    # Setup mock objects
    path = Path(__file__).absolute()
    manifest = manifest_cls()
    data_object = data_object_cls()
    data_object.type = DataType.FILE
    data_object.uri = SimDBUrl(f"file://{path}")
    manifest.inputs = [data_object]
    manifest.outputs = [data_object]
    manifest.metadata = {"description": "test description", "uploaded_by": "test user"}
    sim = Simulation(manifest=manifest)
    assert len(sim.inputs) == 1
    assert sim.inputs[0].type == DataType.FILE
    assert sim.inputs[0].uri == SimDBUrl(f"file://{path}")
    assert len(sim.outputs) == 1
    assert sim.outputs[0].type == DataType.FILE
    assert sim.outputs[0].uri == SimDBUrl(f"file://{path}")
    assert len(sim.meta) == 3
    meta = {m.element: m.value for m in sim.meta}
    assert meta == {
        "description": "test description",
        "status": "not validated",
        "uploaded_by": "test user",
    }


def test_simulation_str_indents_nested_and_multiline_metadata():
    simulation = Simulation(Manifest())
    simulation.set_meta("odd", [{}, [], "", {"a": [{}]}])
    simulation.set_meta("text", "first line\nsecond line\n\nfourth line")
    simulation.set_meta(
        "validation_report",
        {
            "passed": False,
            "tests": {"total": 3, "passed": 2},
            "files": [{"uri": "imas:hdf5?path=/run", "rules": ["a", "b"]}],
        },
    )

    assert (
        "  odd:\n    - \n    - []\n    - \n    - a:\n        - \n"
        "  text: first line\n"
        "        second line\n"
        "\n"
        "        fourth line\n"
        "  validation_report:\n"
        "    passed: False\n"
        "    tests:\n"
        "      total: 3\n"
        "      passed: 2\n"
        "    files:\n"
        "      - uri: imas:hdf5?path=/run\n"
        "        rules: [a, b]\n"
        "inputs:\n"
    ) in str(simulation)


def test_ingestion_error_is_cleared_when_the_ingestion_moves_on():
    simulation = Simulation(Manifest())
    simulation.ingestion_status = IngestionStatus.COPYING
    simulation.fail_ingestion("disk full")

    assert simulation.ingestion_status == IngestionStatus.COPY_FAILED
    assert simulation.ingestion_error == "disk full"

    simulation.ingestion_status = IngestionStatus.COMPLETED

    assert simulation.ingestion_error is None
