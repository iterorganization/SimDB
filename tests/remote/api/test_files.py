import gzip
import hashlib
import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from conftest import (
    HEADERS,
    generate_simulation_data,
    post_simulation,
)

from simdb.cli.manifest import DataObject
from simdb.json import CustomEncoder
from simdb.remote.models import (
    ChunkInfo,
    FileData,
    FileGetDataResponse,
    FileRegistrationData,
    FileRegistrationItem,
    FilesGetResponse,
    FileUploadData,
    SimulationPostData,
)


def create_simulation_with_file(
    client, alias, file_content=b"Test file content for upload"
) -> SimulationPostData:
    chunk_size = 1024
    chunks = [
        file_content[i : i + chunk_size]
        for i in range(0, len(file_content), chunk_size)
    ]
    num_chunks = len(chunks)
    test_checksum = hashlib.sha1(file_content).hexdigest()

    simulation_data = generate_simulation_data(
        alias=alias,
        inputs=[
            FileData(
                type="FILE",
                uri="file:///tmp/test_file.txt",
                checksum=test_checksum,
                datetime=datetime.now(timezone.utc),
            )
        ],
    )

    rv_sim = post_simulation(client, simulation_data)
    assert rv_sim.status_code == 200, rv_sim.data

    # Get the actual file UUID from the simulation (auto-generated)
    file_uuid = simulation_data.simulation.inputs[0].uuid
    for i, chunk in enumerate(chunks):
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz_file:
            gz_file.write(chunk)
        compressed_content = buf.getvalue()

        upload_data = FileUploadData(
            simulation=simulation_data.simulation,
            file_type="input",
            chunk_info={
                file_uuid.hex: ChunkInfo(
                    chunk_size=chunk_size, chunk=i, num_chunks=num_chunks
                )
            },
        )

        _rv_chunk = client.post(
            "/v1.2/files",
            data={
                "data": (
                    io.BytesIO(
                        json.dumps(
                            upload_data.model_dump(mode="json"), cls=CustomEncoder
                        ).encode()
                    ),
                    "data",
                    "text/json",
                ),
                "files": (
                    io.BytesIO(compressed_content),
                    file_uuid.hex,
                    "application/octet-stream",
                ),
            },
            headers=HEADERS,
        )

        # The chunk upload should succeed
        assert _rv_chunk.status_code == 200, _rv_chunk.data

    registration_data = FileRegistrationData(
        simulation=simulation_data.simulation,
        obj_type=DataObject.Type.FILE,
        files=[
            FileRegistrationItem(
                chunks=num_chunks,
                file_type="input",
                file_uuid=file_uuid,
                ids_list=None,
            )
        ],
    )

    rv_register = client.post(
        "/v1.2/files",
        json=registration_data.model_dump(mode="json"),
        headers=HEADERS,
        content_type="application/json",
    )
    assert rv_register.status_code == 200, rv_register.data

    return simulation_data


def test_post_files_endpoint_with_file(client):
    """Test POST /v1.2/files endpoint with single chunk."""
    create_simulation_with_file(client, "test-upload-file")


def test_post_files_endpoint_chunked_upload(client):
    """Test POST /v1.2/files endpoint with multiple chunks."""
    create_simulation_with_file(
        client, "test-upload-file-chunked", file_content=b"Test upload" * 1000
    )


def test_simulation_package_endpoint(client):
    """Test GET /v1.2/simulation/package/{simulation_id} endpoint."""
    test_content = b"test content"
    simulation_data = create_simulation_with_file(
        client, "test-simulation-package", file_content=test_content
    )

    # Test package endpoint
    rv = client.get(
        f"/v1.2/simulation/package/{simulation_data.simulation.uuid.hex}",
        headers=HEADERS,
    )

    assert rv.status_code == 200

    tar_data = io.BytesIO(rv.data)
    with tarfile.open(mode="r:gz", fileobj=tar_data) as tar:
        for member in tar.getmembers():
            if member.isfile():
                assert Path(member.name).name == "test_file.txt"
                data = tar.extractfile(member)
                assert data.read() == test_content


def test_get_files_list(client):
    simulation_data = create_simulation_with_file(client, "test-get-file")

    rv = client.get("/v1.2/files", headers=HEADERS)
    assert rv.status_code == 200

    data = FilesGetResponse.model_validate(rv.json)
    file_uuid = simulation_data.simulation.inputs[0].uuid
    assert any(file_uuid == f.uuid for f in data.root)


def test_get_file_by_uuid(client):
    simulation_data = create_simulation_with_file(client, "test-get-file-by-uuid")

    file_uuid = simulation_data.simulation.inputs[0].uuid
    rv = client.get(f"/v1.2/file/{file_uuid.hex}", headers=HEADERS)
    assert rv.status_code == 200

    FileGetDataResponse.model_validate(rv.json)


@pytest.mark.xfail(reason="File path is not stored correctly?")
def test_download_file(client):
    file_content = b"test data"
    simulation_data = create_simulation_with_file(
        client, "test-get-file-by-uuid", file_content=file_content
    )

    file_uuid = simulation_data.simulation.inputs[0].uuid
    rv = client.get(f"/v1.2/file/download/{file_uuid.hex}", headers=HEADERS)
    assert rv.status_code == 200

    assert rv.data == file_content
