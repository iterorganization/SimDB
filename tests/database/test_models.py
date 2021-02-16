from unittest import mock
from simdb.database.models import Simulation, DataObject


def test_create_simulation_without_manifest_creates_empty_sim():
    sim = Simulation(manifest=None)
    assert sim.id is None
    assert sim.uuid is None
    assert sim.alias is None
    assert sim.datetime is None
    assert sim.status is None
    assert sim.inputs == []
    assert sim.outputs == []
    assert sim.meta == []
    assert sim.provenance is None
    assert sim.summary == []


@mock.patch('simdb.database.models.DataObject')
@mock.patch('simdb.cli.manifest.Manifest')
def test_create_simulation_with_manifest(manifest_cls, data_object_cls):
    manifest = manifest_cls()
    data_object = data_object_cls()
    data_object.type = data_object_cls.Type.FILE
    data_object.path = '/test/file/path.txt'
    manifest.inputs = [data_object]
    manifest.outputs = [data_object]
    manifest.workflow = {}
    manifest.description = 'test description'
    sim = Simulation(manifest=manifest)
    assert len(sim.inputs) == 1
    assert sim.inputs[0].type == data_object_cls.Type.FILE
    assert sim.inputs[0].directory == '/test/file'
    assert sim.inputs[0].file_name == 'path.txt'
    assert len(sim.outputs) == 1
    assert sim.outputs[0].type == data_object_cls.Type.FILE
    assert sim.outputs[0].directory == '/test/file'
    assert sim.outputs[0].file_name == 'path.txt'
    assert len(sim.meta) == 1
    assert sim.meta[0].element == 'description'
    assert sim.meta[0].value == 'test description'
