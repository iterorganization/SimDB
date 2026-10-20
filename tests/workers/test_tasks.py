from datetime import datetime, timezone
from unittest import mock
from uuid import uuid1

import pytest

from simdb.checksum import calculate_checksum
from simdb.config import Config
from simdb.database.models import Simulation
from simdb.enums import IngestionStatus
from simdb.imas.utils import SimDBUrl
from simdb.remote.models import FileData
from simdb.validation import MetadataReport, ValidationReport
from simdb.workers import tasks as simdb_tasks
from simdb.workers.tasks import (
    _copy_files,
    _create_file_from_data,
    _get_imas_identifier_path,
    _imas_path_to_uri,
    _notify_watchers,
    _resolve_paths,
    _resolve_uri_to_path,
    copy_files_task,
    validate_simulation_task,
)


def _make_file_data(uri: str, checksum: str = "abc") -> FileData:
    return FileData(
        type="FILE",
        uri=uri,
        checksum=checksum,
        datetime=datetime.now(timezone.utc),
    )


def test_get_imas_identifier_path_returns_file_for_netcdf(tmp_path):
    nc_file = tmp_path / "data.nc"
    nc_file.touch()

    assert _get_imas_identifier_path(nc_file) == nc_file


def test_get_imas_identifier_path_returns_parent_for_directory(tmp_path):
    ids_dir = tmp_path / "ids_dir"
    ids_dir.mkdir()

    assert _get_imas_identifier_path(ids_dir) == tmp_path


@pytest.mark.parametrize(
    "files,expected_backend",
    [
        (["summary.ids"], "ascii"),
        (["master.h5", "summary.h5"], "hdf5"),
        (["ids_001.tree", "ids_001.characteristics", "ids_001.datafile"], "mdsplus"),
    ],
)
def test_imas_path_to_uri_detects_backend_from_directory(
    tmp_path, files, expected_backend
):
    ids_dir = tmp_path / "ids_dir"
    ids_dir.mkdir()
    for f in files:
        (ids_dir / f).touch()

    uri = _imas_path_to_uri(ids_dir)

    assert uri.scheme == "imas"
    assert uri.path == expected_backend
    assert dict(uri.query_params())["path"] == str(ids_dir)


def test_imas_path_to_uri_unknown_backend_raises(tmp_path):
    ids_dir = tmp_path / "ids_dir"
    ids_dir.mkdir()
    (ids_dir / "file1.txt").touch()

    with pytest.raises(ValueError, match="IMAS backend could not be identified"):
        _imas_path_to_uri(ids_dir)


@pytest.fixture
def config_with_partition(tmp_path):
    config = Config()
    partition_path = tmp_path / "partition_data"
    partition_path.mkdir()
    config.set_option("partition.data", str(partition_path))
    return config, partition_path


def test_resolve_uri_to_path_returns_partition_relative_path(config_with_partition):
    config, partition_path = config_with_partition

    result = _resolve_uri_to_path(SimDBUrl("data:/subdir/file.txt"), config)

    assert result == partition_path / "subdir" / "file.txt"


def test_resolve_uri_to_path_unknown_partition_raises(config_with_partition):
    config, _ = config_with_partition

    with pytest.raises(ValueError, match="Partition 'unknown' not found"):
        _resolve_uri_to_path(SimDBUrl("unknown:/file.txt"), config)


def test_resolve_paths_resolves_multiple_files(config_with_partition):
    config, partition_path = config_with_partition
    files = [_make_file_data("data:/file1.txt"), _make_file_data("data:/file2.txt")]

    result = _resolve_paths(files, config)

    assert result == [partition_path / "file1.txt", partition_path / "file2.txt"]


@pytest.mark.parametrize(
    "relative_source,common_root_subpath,expected_dst_subpath",
    [
        ("source.txt", "", "source.txt"),
        ("source/subdir/file.txt", "source", "subdir/file.txt"),
        ("source/nested/file.txt", "source", "nested/file.txt"),
    ],
)
def test_copy_files_preserves_relative_layout(
    tmp_path, relative_source, common_root_subpath, expected_dst_subpath
):
    source = tmp_path / relative_source
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("content")

    common_root = tmp_path / common_root_subpath
    dst_basepath = tmp_path / "dest"

    _copy_files([source], common_root, dst_basepath)

    destination = dst_basepath / expected_dst_subpath
    assert destination.exists()
    assert destination.read_text() == "content"


def test_create_file_from_data_raises_on_checksum_mismatch(tmp_path):
    config = Config()
    partition_path = tmp_path / "partition_data"
    partition_path.mkdir()
    config.set_option("partition.data", str(partition_path))
    data_file = partition_path / "testfile.txt"
    data_file.write_text("content")

    file_data = _make_file_data("data:testfile.txt", checksum="wrong_checksum")

    with pytest.raises(ValueError, match="Hash of file does not match"):
        _create_file_from_data(file_data, config, data_file)


@pytest.fixture
def task_environment(tmp_path):
    """Set up Config, mocked DB, and directory layout for copy_files_task tests."""
    config = Config()
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    partition_dir = tmp_path / "partition"
    partition_dir.mkdir()

    config.set_option("database.type", "sqlite")
    config.set_option("database.file", str(tmp_path / "test.db"))
    config.set_option("server.upload_folder", str(upload_dir))
    config.set_option("partition.data", str(partition_dir))
    config.load = mock.MagicMock()

    simulation_uuid = uuid1()
    mock_simulation = mock.MagicMock(uuid=simulation_uuid, inputs=[], outputs=[])
    mock_db = mock.MagicMock()
    mock_db.get_simulation.return_value = mock_simulation

    with mock.patch("simdb.workers.tasks.Config", return_value=config), mock.patch(
        "simdb.workers.tasks.get_db", return_value=mock_db
    ):
        yield {
            "config": config,
            "upload_dir": upload_dir,
            "partition_dir": partition_dir,
            "simulation_uuid": simulation_uuid,
            "simulation": mock_simulation,
            "db": mock_db,
        }


def test_copy_files_task_copies_inputs_and_marks_copied(task_environment):
    env = task_environment
    source_file = env["partition_dir"] / "source.txt"
    source_file.write_text("test content")

    input_files = [
        _make_file_data(
            f"data:/{source_file.name}", checksum=calculate_checksum(source_file)
        )
    ]

    copy_files_task(env["simulation_uuid"], input_files, [])

    expected_destination = env["upload_dir"] / env["simulation_uuid"].hex / "source.txt"
    assert expected_destination.read_text() == "test content"
    assert env["simulation"].ingestion_status == IngestionStatus.COPIED
    env["db"].session.add.assert_called()


def test_copy_files_task_with_no_files_marks_copied(task_environment):
    env = task_environment

    copy_files_task(env["simulation_uuid"], [], [])

    assert env["simulation"].ingestion_status == IngestionStatus.COPIED


def test_notify_watchers_queues_email_when_watchers_present():
    watcher = mock.MagicMock(email="watcher@example.com")
    simulation = mock.MagicMock(watchers=[watcher])

    with mock.patch.object(simdb_tasks.send_email_task, "delay") as delay:
        _notify_watchers(simulation, "subject", "body")

    delay.assert_called_once_with("subject", "body", ["watcher@example.com"])


def test_notify_watchers_noop_without_watchers():
    simulation = mock.MagicMock(watchers=[])

    with mock.patch.object(simdb_tasks.send_email_task, "delay") as delay:
        _notify_watchers(simulation, "subject", "body")

    delay.assert_not_called()


def test_copy_files_task_records_why_the_copy_failed(task_environment):
    env = task_environment
    source_file = env["partition_dir"] / "source.txt"
    source_file.write_text("test content")
    input_files = [_make_file_data(f"data:/{source_file.name}", checksum="wrong")]

    with pytest.raises(ValueError, match="Hash of file does not match"):
        copy_files_task(env["simulation_uuid"], input_files, [])

    (reason,), _ = env["simulation"].fail_ingestion.call_args
    assert "Hash of file does not match" in reason


def test_copy_files_task_keeps_server_details_out_of_the_reason(task_environment):
    """An error in the server's own setup is reported to the client by type
    only; the details stay in the worker log."""
    env = task_environment
    source_file = env["partition_dir"] / "source.txt"
    source_file.write_text("test content")
    input_files = [
        _make_file_data(
            f"data:/{source_file.name}", checksum=calculate_checksum(source_file)
        )
    ]
    error = PermissionError(13, "Permission denied", "/srv/simdb/uploads/secret")

    with mock.patch(
        "simdb.workers.tasks._copy_files", side_effect=error
    ), pytest.raises(PermissionError):
        copy_files_task(env["simulation_uuid"], input_files, [])

    (reason,), _ = env["simulation"].fail_ingestion.call_args
    assert reason.startswith("PermissionError while copying the files")
    assert "/srv/simdb" not in reason


def test_validate_simulation_task_records_a_passed_validation(task_environment):
    env = task_environment
    report = ValidationReport(metadata=MetadataReport())

    with mock.patch(
        "simdb.workers.tasks.validate_simulation", return_value=report
    ) as validate, mock.patch.object(
        simdb_tasks.send_email_task, "delay"
    ) as delay, mock.patch("simdb.workers.tasks.clear_api_cache_from_worker") as clear:
        validate_simulation_task(env["simulation_uuid"])

    validate.assert_called_once_with(env["simulation"], env["config"])
    assert env["simulation"].status == Simulation.Status.PASSED
    env["simulation"].set_meta.assert_called_once_with(
        "validation_report", report.to_dict()
    )
    # The API may have cached the simulation before the outcome was recorded.
    clear.assert_called_once_with(env["config"])
    delay.assert_not_called()
    env["db"].close.assert_called_once()


def test_copy_files_task_clears_the_api_cache(task_environment):
    """The copied files are only visible through the API once its cache of the
    simulation has been emptied."""
    env = task_environment
    source_file = env["partition_dir"] / "source.txt"
    source_file.write_text("test content")
    input_files = [
        _make_file_data(
            f"data:/{source_file.name}", checksum=calculate_checksum(source_file)
        )
    ]

    with mock.patch("simdb.workers.tasks.clear_api_cache_from_worker") as clear:
        copy_files_task(env["simulation_uuid"], input_files, [])

    clear.assert_called_once_with(env["config"])


def test_validate_simulation_task_records_a_failed_validation(task_environment):
    """A failed validation is kept with the simulation and does not touch the
    ingestion, which has already completed."""
    env = task_environment
    env["simulation"].ingestion_status = IngestionStatus.COMPLETED
    watcher = mock.MagicMock(email="watcher@example.com")
    env["simulation"].watchers = [watcher]
    report = ValidationReport(metadata=MetadataReport(error="rule X failed"))

    with mock.patch(
        "simdb.workers.tasks.validate_simulation", return_value=report
    ), mock.patch.object(simdb_tasks.send_email_task, "delay") as delay:
        validate_simulation_task(env["simulation_uuid"])

    assert env["simulation"].status == Simulation.Status.FAILED
    assert env["simulation"].ingestion_status == IngestionStatus.COMPLETED
    env["simulation"].set_meta.assert_called_once_with(
        "validation_report", report.to_dict()
    )
    subject, body, to_addresses = delay.call_args.args
    assert "failed validation" in subject
    assert "rule X failed" in body
    assert to_addresses == ["watcher@example.com"]
    env["db"].close.assert_called_once()


def test_validate_simulation_task_records_a_validation_that_could_not_run(
    task_environment,
):
    """A validator that cannot run (not installed, misconfigured) is a failed
    validation with the reason on the simulation, not only in the worker log.
    The watchers are not emailed: it is the operator's problem, not theirs."""
    env = task_environment
    env["simulation"].watchers = [mock.MagicMock(email="watcher@example.com")]

    with mock.patch(
        "simdb.workers.tasks.validate_simulation",
        side_effect=RuntimeError("IMAS-validator not available"),
    ), mock.patch.object(simdb_tasks.send_email_task, "delay") as delay:
        validate_simulation_task(env["simulation_uuid"])

    assert env["simulation"].status == Simulation.Status.FAILED
    report = env["simulation"].set_meta.call_args.args[1]
    assert report["passed"] is False
    assert report["error"] == "RuntimeError: IMAS-validator not available"
    delay.assert_not_called()
    env["db"].close.assert_called_once()
