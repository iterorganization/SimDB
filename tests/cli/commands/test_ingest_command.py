from unittest import mock
from simdb.cli.commands import IngestCommand


def test_create_ingest_command():
    IngestCommand()


@mock.patch('argparse.ArgumentParser')
def test_ingest_command_add_args(parser):
    cmd = IngestCommand()
    cmd.add_arguments(parser)
    parser.add_argument.assert_any_call("manifest_file", help="manifest file location")
    parser.add_argument.assert_any_call("--alias", "-a", help="alias of an existing manifest to update, or a new alias use")
    parser.add_argument.assert_any_call("--uuid", "-u", help="uuid of an already ingested manifest to update")
    parser.add_argument.assert_any_call("--update", action="store_true", help="update an existing manifest")


@mock.patch('simdb.database.models.Simulation')
@mock.patch('simdb.cli.manifest.Manifest')
@mock.patch('simdb.database.database.get_local_db')
def test_ingest_run(get_local_db, manifest_cls, simulation_cls):
    import uuid
    cmd = IngestCommand()
    args = IngestCommand.IngestArgs()
    args.manifest_file = 'test.yaml'
    args.alias = 'test-alias'
    args.uuid = uuid.UUID('123e4567-e89b-12d3-a456-426655440000')
    config = ('test',)
    cmd.run(args, config)

    # 1. Manifest file loaded from args.manifest_file
    manifest_cls.assert_called_once()
    manifest = manifest_cls.return_value
    manifest.load.assert_called_once_with(args.manifest_file)
    manifest.validate.assert_called_once()

    # 2. Simulation created form manifest
    simulation_cls.assert_called_once_with(manifest)
    simulation = simulation_cls.return_value
    assert simulation.alias == args.alias
    assert simulation.uuid == args.uuid

    # 3. Simulation inserted into database
    get_local_db.assert_called_once_with(config)
    db = get_local_db.return_value
    db.insert_simulation.assert_called_once_with(simulation)

