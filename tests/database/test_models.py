from unittest import mock
from uri import URI
from simdb.database.models import Simulation
from simdb.cli.manifest import DataObject
from pathlib import Path


def test_create_simulation_without_manifest_creates_empty_sim():
    sim = Simulation(manifest=None)
    assert sim.id is None
    assert sim.uuid is None
    assert sim.alias is None
    assert sim.inputs == []
    assert sim.outputs == []
    assert sim.meta == []


@mock.patch('simdb.cli.manifest.DataObject')
@mock.patch('simdb.cli.manifest.Manifest')
def test_create_simulation_with_manifest(manifest_cls, data_object_cls):
    path = Path(__file__).absolute()
    manifest = manifest_cls()
    data_object = data_object_cls()
    data_object.type = DataObject.Type.FILE
    data_object.uri = URI(f'file://{path}')
    manifest.inputs = [data_object]
    manifest.outputs = [data_object]
    manifest.metadata = {
        'description': 'test description'
    }
    sim = Simulation(manifest=manifest)
    assert len(sim.inputs) == 1
    assert sim.inputs[0].type == DataObject.Type.FILE
    assert sim.inputs[0].uri == URI(f'file://{path}')
    assert len(sim.outputs) == 1
    assert sim.outputs[0].type == DataObject.Type.FILE
    assert sim.outputs[0].uri == URI(f'file://{path}')
    assert len(sim.meta) == 2
    meta = {m.element: m.value for m in sim.meta}
    assert meta == {'description': 'test description', 'status': 'not validated'}
