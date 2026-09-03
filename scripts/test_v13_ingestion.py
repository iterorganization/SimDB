#!/usr/bin/env python3
"""Test script for v1.3 simulation ingestion against a running server."""
from simdb.checksum import calculate_checksum
from pathlib import Path

import base64
import sys
import time
import uuid
from datetime import datetime, timezone

import requests
from pydantic import TypeAdapter

try:
    from simdb.remote.models import (
        FileData,
        FileDataList,
        MetadataData,
        MetadataDataList,
        SimulationData,
        SimulationPostData,
        SimulationPostResponse,
        SimulationStatusResponse,
    )
except ImportError:
    print("ERROR: simdb package not installed. Run: pip install -e .")
    sys.exit(1)

SERVER_URL = "http://localhost:5000"
API_VERSION = "v1.3"
API_VERSION_V12 = "v1.2"
TEST_PASSWORD = "CHANGE_ME"

CREDENTIALS = base64.b64encode(f"admin:{TEST_PASSWORD}".encode()).decode()
HEADERS = {"Authorization": f"Basic {CREDENTIALS}"}


def generate_simulation_file():
    checksum = calculate_checksum(Path("tmp/partition_data/subdir/test_file.txt"))
    return FileData(
        type="FILE",
        uri="data:///subdir/test_file.txt",
        checksum=checksum,
        datetime=datetime.now(timezone.utc),
    )

def generate_imas_file(relative_path):
    checksum = calculate_checksum(Path(f"tmp/partition_data/subdir/{relative_path}"))
    return FileData(
        type="IMAS",
        uri=f"data:///subdir/{relative_path}",
        checksum=checksum,
        datetime=datetime.now(timezone.utc),
    )


def generate_imas_netcdf_file():
    return generate_imas_file("test_imas_data/test.nc")


def generate_imas_hdf5_files():
    return [
        generate_imas_file("test_imas_data/test_hdf5/master.h5"),
        generate_imas_file("test_imas_data/test_hdf5/summary.h5"),
    ]


def generate_imas_mdsplus_files():
    return [
        generate_imas_file("test_imas_data/test_mdsplus/ids_001.characteristics"),
        generate_imas_file("test_imas_data/test_mdsplus/ids_001.datafile"),
        generate_imas_file("test_imas_data/test_mdsplus/ids_001.tree"),
    ]


def generate_all_imas_files():
    return [
        generate_imas_file("test_imas_data/test.nc"),
        *generate_imas_hdf5_files(),
        *generate_imas_mdsplus_files(),
    ]


def generate_simulation_data(
    alias=None,
    inputs=None,
    outputs=None,
    metadata=None,
    add_watcher=False,
    uploaded_by=None,
):
    if alias is None:
        alias = f"test-{uuid.uuid4().hex[:8]}"
    if inputs is None:
        inputs = [generate_simulation_file()]
    if outputs is None:
        outputs = [generate_simulation_file()]

    simulation = SimulationData(
        alias=alias,
        inputs=FileDataList(root=inputs),
        outputs=FileDataList(root=outputs),
    )

    if metadata:
        simulation.metadata = MetadataDataList(root=metadata)

    data = SimulationPostData(
        simulation=simulation,
        add_watcher=add_watcher,
        uploaded_by=uploaded_by,
    )
    return data


def post_simulation(simulation_data, retries=5, delay=2):
    url = f"{SERVER_URL}/{API_VERSION}/simulations"
    for attempt in range(retries):
        try:
            response = requests.post(
                url,
                json=simulation_data.model_dump(mode="json"),
                headers={**HEADERS, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise


def get_simulation_status(sim_id):
    url = f"{SERVER_URL}/{API_VERSION}/simulation/status/{sim_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response


def get_simulation(sim_id):
    url = f"{SERVER_URL}/{API_VERSION_V12}/simulation/{sim_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response


def verify_files_in_database(sim_id, expected_files):
    response = get_simulation(sim_id)
    sim_data = response.json()
    all_files = sim_data.get("inputs", []) + sim_data.get("outputs", [])
    stored_uris = {f["uri"] for f in all_files}
    expected_uris = expected_files
    missing = expected_uris - stored_uris
    return stored_uris, missing


def wait_for_completion(sim_id, timeout=60, interval=2):
    start = time.time()
    while time.time() - start < timeout:
        response = get_simulation_status(sim_id)
        status_data = SimulationStatusResponse.model_validate(response.json())
        print(f"  Status: {status_data.status}")
        if status_data.status.name in ("COMPLETED", "COPY_FAILED"):
            return status_data
        time.sleep(interval)
    raise TimeoutError(f"Simulation {sim_id} did not complete within {timeout}s")


def main():
    print("=" * 60)
    print("v1.3 Simulation Ingestion Test")
    print("=" * 60)
    print(f"Server: {SERVER_URL}")
    print(f"API Version: {API_VERSION}")
    print()

    print("Generating simulation data...")
    imas_files = generate_all_imas_files()
    simulation_data = generate_simulation_data(
        alias=f"test-ingestion-{uuid.uuid4().hex}",
        inputs=[generate_simulation_file()],
        outputs=imas_files,
        uploaded_by="test-script",
    )
    print(f"  Alias: {simulation_data.simulation.alias}")
    print(f"  UUID: {simulation_data.simulation.uuid}")
    print(f"  Files: {len(simulation_data.simulation.inputs.root)+len(simulation_data.simulation.outputs.root)}")
    print()

    print("Posting simulation for ingestion...")
    try:
        response = post_simulation(simulation_data, retries=1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to post simulation: {e}")
        sys.exit(1)

    result = SimulationPostResponse.model_validate(response.json())
    print(f"  Ingested UUID: {result.ingested}")
    if result.error:
        print(f"  Error: {result.error}")
    print()

    print("Waiting for ingestion to complete...")
    try:
        final_status = wait_for_completion(result.ingested)
        print()
        print("=" * 60)
        print(f"SUCCESS: Ingestion completed with status {final_status.status}")
        print("=" * 60)

        print()
        print("Verifying files in database via v1.2 API...")
        imas_paths = {
            f"file:/data/simdb/simulations/{result.ingested.hex}/test_file.txt",
            f"file:/data/simdb/simulations/{result.ingested.hex}/test_imas_data/test.nc",
            f"imas:hdf5?path=/data/simdb/simulations/{result.ingested.hex}/test_imas_data/test_hdf5",
            f"imas:mdsplus?path=/data/simdb/simulations/{result.ingested.hex}/test_imas_data/test_mdsplus",
        }
        stored_uris, missing = verify_files_in_database(result.ingested, imas_paths)
        print(f"  Stored URIs: {len(stored_uris)}")
        for uri in sorted(stored_uris):
            print(f"    {uri}")
        if missing:
            print(f"  MISSING files: {missing}")
        else:
            print("  All files verified!")
    except TimeoutError as e:
        print()
        print("=" * 60)
        print(f"WARNING: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
