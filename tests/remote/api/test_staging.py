import hashlib
import uuid
from datetime import datetime, timezone

from conftest import HEADERS, generate_simulation_data, post_simulation

from simdb.remote.models import FileData, StagingDirectoryResponse


def test_get_staging_dir(client):
    """Test GET /v1.2/staging_dir endpoint - get base staging directory."""
    rv = client.get("/v1.2/staging_dir", headers=HEADERS)

    assert rv.status_code == 200
    StagingDirectoryResponse.model_validate(rv.json)


def test_get_staging_dir_for_simulation_with_uuid(client):
    """Test GET /v1.2/staging_dir/{sim_hex} endpoint with valid UUID hex."""
    valid_uuid = uuid.uuid4().hex

    rv = client.get(f"/v1.2/staging_dir/{valid_uuid}", headers=HEADERS)

    assert rv.status_code == 200
    StagingDirectoryResponse.model_validate(rv.json)


def test_create_simulation_from_staging_dir(client_copy_files):
    file_data = b"test_data"
    checksum = hashlib.sha1(file_data).hexdigest()
    simulation_data = generate_simulation_data(
        alias="test-simulation",
        inputs=[
            FileData(
                type="FILE",
                uri="file:///path/to/file",
                checksum=checksum,
                datetime=datetime.now(timezone.utc),
            )
        ],
    )

    rv = client_copy_files.get(
        f"/v1.2/staging_dir/{simulation_data.simulation.uuid.hex}", headers=HEADERS
    )

    assert rv.status_code == 200
    staging_data = StagingDirectoryResponse.model_validate(rv.json)

    # Store the file in the staging area
    (staging_data.staging_dir / "file").write_bytes(file_data)

    rv = post_simulation(client_copy_files, simulation_data)
    assert rv.status_code == 200, rv.data
