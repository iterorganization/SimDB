import itertools
import logging
import os
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Iterable, List
from uuid import UUID

from simdb.checksum import hash_file
from simdb.config import Config
from simdb.database.database import get_db
from simdb.database.models import File
from simdb.email.server import EmailServer
from simdb.enums import IngestionStatus
from simdb.imas.utils import SimDBUrl, imas_backend_for_directory
from simdb.remote.models import FileData, FileDataList
from simdb.workers.celery import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def send_email_task(
    subject: str,
    body: str,
    to_addresses: List[str],
) -> dict:
    config = Config()
    config.load()

    email_server = EmailServer(config)
    email_server.send_message(subject, body, to_addresses)

    return {
        "status": "sent",
        "subject": subject,
        "recipients": to_addresses,
    }


_EMAIL_FOOTER = (
    "\n\nNote: please don't reply to this email, replies to this address are "
    "not monitored."
)


def _simulation_label(simulation) -> str:
    return simulation.alias or simulation.uuid.hex


def _notify_watchers(simulation, subject: str, message: str) -> None:
    """Queue an email to a simulation's watchers, if it has any."""
    to_addresses = [watcher.email for watcher in simulation.watchers]
    if to_addresses:
        send_email_task.delay(subject, message, to_addresses)


def _imas_path_to_uri(imas_path: Path) -> SimDBUrl:
    if imas_path.suffix == ".nc":
        return SimDBUrl.build(scheme="file", path=imas_path.as_posix())

    backend = imas_backend_for_directory(imas_path)

    return SimDBUrl.build(
        scheme="imas", path=backend, query=f"path={imas_path.as_posix()}"
    )


def _resolve_uri_to_path(uri: SimDBUrl, config: Config) -> Path:
    partition = uri.scheme
    if not partition:
        raise ValueError("Partition not given")
    partition_path_str = config.get_string_option(
        f"partition.{partition}", default=None
    )
    if not partition_path_str:
        raise ValueError(f"Partition '{partition}' not found in config")
    partition_path = Path(partition_path_str)
    path = uri.path
    if not path:
        raise ValueError("Path not given")
    path = Path(path)
    path = path.relative_to(path.anchor)
    # Standard schemes (e.g. ``http``) parse the first path segment as the URL
    # authority. Fold it back in so the full relative path is reconstructed.
    if uri.host:
        path = Path(uri.host) / path
    target = (partition_path / path).resolve()
    if not target.is_relative_to(partition_path):
        raise ValueError("Access denied.")
    return target


def _resolve_paths(files_data: list[FileData], config: Config) -> list[Path]:
    return [_resolve_uri_to_path(SimDBUrl(f.uri), config) for f in files_data]


def _resolve_destination_path(
    source: Path, common_root: Path, dst_basepath: Path
) -> Path:
    return dst_basepath / source.relative_to(common_root)


def _copy_files(
    paths: Iterable[Path],
    common_root: Path,
    dst_basepath: Path,
):
    for source in paths:
        destination = _resolve_destination_path(source, common_root, dst_basepath)
        destination.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy2(source, destination)


def _checksum_matches(path: Path, expected: str) -> bool:
    """Whether ``path`` matches ``expected``."""
    return hash_file(path) == expected


def _get_imas_identifier_path(path: Path) -> Path:
    if path.suffix == ".nc":
        return path
    return path.parent


def _create_file_from_data(
    data: FileData, config: Config, imas_identifier_path: Path
) -> File:
    uri = SimDBUrl(data.uri)
    path = _resolve_uri_to_path(uri, config)

    if not _checksum_matches(path, data.checksum):
        raise ValueError("Hash of file does not match provided checksum")

    file = File.from_data_model(data)
    file.uri = _imas_path_to_uri(imas_identifier_path)

    return file


def _create_files_from_data_list(
    files_data: list[FileData], config: Config, common_root: Path, dst_basepath: Path
) -> list[File]:
    seen_imas_paths: set[Path] = set()
    files: list[File] = []

    for file_data in files_data:
        uri = SimDBUrl(file_data.uri)
        path = _resolve_destination_path(
            _resolve_uri_to_path(uri, config), common_root, dst_basepath
        )

        if file_data.type == "IMAS":
            imas_path = _get_imas_identifier_path(path)
            if imas_path in seen_imas_paths:
                continue
            seen_imas_paths.add(imas_path)
            file = _create_file_from_data(file_data, config, imas_path)
        else:
            if not _checksum_matches(path, file_data.checksum):
                raise ValueError("Hash of file does not match provided checksum")
            file = File.from_data_model(file_data)
            file.uri = SimDBUrl.build(scheme="file", path=path.as_posix())

        files.append(file)

    return files


@celery_app.task
def copy_files_task(
    simulation_uuid: UUID,
    input_files_d: list[FileData],
    output_files_d: list[FileData],
):
    input_files = FileDataList.model_validate(input_files_d).root
    output_files = FileDataList.model_validate(output_files_d).root
    config = Config()
    config.load()
    database = get_db(config)

    simulation = database.get_simulation(simulation_uuid.hex)
    simulation.ingestion_status = IngestionStatus.COPYING
    database.session.commit()

    try:
        input_paths = _resolve_paths(input_files, config)
        output_paths = _resolve_paths(output_files, config)
        paths = set(input_paths + output_paths)
        if len(paths) == 0:
            common_root = Path()
        elif len(paths) == 1:
            common_root = next(iter(paths)).parent
        else:
            common_root = Path(os.path.commonpath(paths))
        dst_basepath: Path = (
            Path(config.get_string_option("server.upload_folder")) / simulation_uuid.hex
        )

        _copy_files(paths, common_root, dst_basepath)

        inputs = _create_files_from_data_list(
            input_files, config, common_root, dst_basepath
        )
        outputs = _create_files_from_data_list(
            output_files, config, common_root, dst_basepath
        )

        for f in [*inputs, *outputs]:
            database.session.add(f)

        simulation.inputs = inputs
        simulation.outputs = outputs
        simulation.ingestion_status = IngestionStatus.COPIED
        database.session.commit()
    except Exception:
        simulation.ingestion_status = IngestionStatus.COPY_FAILED
        database.session.commit()
        label = _simulation_label(simulation)
        _notify_watchers(
            simulation,
            f"Simulation {label} ingestion failed",
            f"Ingestion of simulation {label} failed while copying files. "
            f"Please check the uploaded files and try again.{_EMAIL_FOOTER}",
        )
        raise
    finally:
        database.close()


@celery_app.task
def validate_imas_task(simulation_uuid: UUID):
    config = Config()
    config.load()
    database = get_db(config)

    try:
        simulation = database.get_simulation(simulation_uuid.hex)
        simulation.ingestion_status = IngestionStatus.VALIDATING
        database.session.commit()

        for _file in itertools.chain(simulation.inputs, simulation.outputs):
            # TODO
            pass

        simulation.ingestion_status = IngestionStatus.VALIDATED
        database.session.commit()
    finally:
        database.close()


@celery_app.task
def complete_ingestion_task(simulation_uuid: UUID):
    config = Config()
    config.load()
    database = get_db(config)

    try:
        simulation = database.get_simulation(simulation_uuid.hex)
        simulation.ingestion_status = IngestionStatus.COMPLETED
        database.session.commit()

        label = _simulation_label(simulation)
        _notify_watchers(
            simulation,
            f"Simulation {label} ingested",
            f"Simulation {label} has been successfully ingested into "
            f"SimDB.{_EMAIL_FOOTER}",
        )
    finally:
        database.close()


@celery_app.task
def fail_stale_ingestions_task() -> dict:
    """Periodic sweep that fails simulations stuck in a non-terminal ingestion
    state.
    """
    config = Config()
    config.load()
    database = get_db(config)

    try:
        timeout = config.get_int_option("celery.stale_ingestion_timeout", default=7200)
        failed = database.fail_stale_ingestions(timedelta(seconds=timeout))
        if failed:
            logger.warning("Marked %d stale ingestion(s) as failed", failed)
        return {"failed": failed}
    finally:
        database.close()


@celery_app.task
def cleanup_http_staging_task(simulation_uuid: UUID):
    """Remove a simulation's staged files from the ``http`` partition.

    HTTP-uploaded files are staged into the ``http`` partition and then copied
    into the simulation's upload folder by :func:`copy_files_task`. Once copied
    they are duplicates, so the staging directory is removed here.
    """
    config = Config()
    config.load()

    partition_path_str = config.get_string_option("partition.http", default=None)
    if not partition_path_str:
        return

    partition_path = Path(partition_path_str).resolve()
    staging_dir = (partition_path / simulation_uuid.hex).resolve()
    # Guard against escaping the partition before removing anything.
    if staging_dir.is_relative_to(partition_path) and staging_dir != partition_path:
        shutil.rmtree(staging_dir, ignore_errors=True)
