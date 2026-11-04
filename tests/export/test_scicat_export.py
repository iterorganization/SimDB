from datetime import datetime, timezone
from typing import Dict, List
from uuid import UUID

import pytest

scitacean = pytest.importorskip("scitacean")

from scitacean import Profile  # noqa: E402
from scitacean.testing.client import FakeClient  # noqa: E402

from simdb.export.scicat import (  # noqa: E402
    ExportOptions,
    export_simulations,
    simulation_to_dataset,
)
from simdb.remote.models import SimulationDataResponse  # noqa: E402

PARENT_UUID = UUID("11111111-1111-1111-1111-111111111111")
CHILD_UUID = UUID("22222222-2222-2222-2222-222222222222")
NO_FILES_UUID = UUID("33333333-3333-3333-3333-333333333333")

OPTIONS = ExportOptions(
    owner_group="imas",
    contact_email="imas-support@iter.org",
    simdb_url="https://simdb.iter.org/scenarios/api",
)


def _file(uri: str, file_type: str = "FILE") -> dict:
    return {
        "type": file_type,
        "uri": uri,
        "checksum": "abc",
        "datetime": "2026-01-01T00:00:00",
    }


def _sim(uuid: UUID, alias: str, *, parents=(), outputs=None, metadata=None):
    return SimulationDataResponse.model_validate(
        {
            "uuid": uuid,
            "alias": alias,
            "datetime": "2026-03-04T05:06:07",
            "inputs": [_file("file:///work/inputs/input.yaml")],
            "outputs": (
                [_file("imas:hdf5?path=/work/imas/run1", "IMAS")]
                if outputs is None
                else outputs
            ),
            "metadata": metadata
            if metadata is not None
            else [
                {"element": "description", "value": "A test scenario"},
                {"element": "code.name", "value": "astra"},
                {"element": "code.version", "value": "7.1"},
                {"element": "uploaded_by", "value": "jdoe"},
                {"element": "global_quantities.ip", "value": {"min": 1.0, "max": 15.0}},
            ],
            "parents": [{"uuid": p, "alias": None} for p in parents],
            "children": [],
        }
    )


class FakeSource:
    def __init__(self, sims: List[SimulationDataResponse]):
        self.sims: Dict[str, SimulationDataResponse] = {str(s.uuid): s for s in sims}

    def list_simulation_ids(self) -> List[str]:
        return list(self.sims)

    def get_simulation(self, sim_id: str) -> SimulationDataResponse:
        return self.sims[sim_id]


class QueryableFakeClient(FakeClient):
    """FakeClient plus the keyword query the exporter uses to find earlier exports.

    Scitacean's FakeClient does not implement ``query_datasets``.
    """

    def __init__(self):
        super().__init__(
            profile=Profile(url="https://scicat.test/api/v3", file_transfer=None)
        )
        scicat = self.scicat
        datasets = self.datasets

        def query_datasets(fields, **_kwargs):
            wanted = set(fields["keywords"])
            return [d for d in datasets.values() if wanted <= set(d.keywords or [])]

        scicat.query_datasets = query_datasets  # type: ignore[method-assign]


def _exported(client) -> Dict[str, object]:
    return {d.scientificMetadata["simdb"]["uuid"]: d for d in client.datasets.values()}


def test_simulation_maps_to_derived_dataset():
    dataset = simulation_to_dataset(_sim(PARENT_UUID, "parent"), OPTIONS)

    assert dataset.type == "derived"
    assert dataset.name == "parent"
    assert dataset.description == "A test scenario"
    assert dataset.owner == "jdoe"
    assert dataset.owner_group == "imas"
    assert dataset.contact_email == "imas-support@iter.org"
    assert dataset.creation_time == datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
    assert dataset.source_folder == "/work/imas/run1"
    assert dataset.used_software == ["astra 7.1"]
    assert dataset.data_format == "IMAS"
    assert f"simdb:{PARENT_UUID}" in dataset.keywords


def test_scientific_metadata_keeps_simdb_metadata_and_identity():
    dataset = simulation_to_dataset(_sim(PARENT_UUID, "parent"), OPTIONS)

    meta = dataset.meta
    assert meta["code"] == {"name": "astra", "version": "7.1"}
    assert meta["global_quantities"] == {"ip": {"min": 1.0, "max": 15.0}}
    assert meta["simdb"]["uuid"] == str(PARENT_UUID)
    assert meta["simdb"]["alias"] == "parent"
    assert meta["simdb"]["server"] == "https://simdb.iter.org/scenarios/api"
    assert meta["simdb"]["outputs"] == ["imas:hdf5?path=/work/imas/run1"]
    assert meta["simdb"]["inputs"] == ["file:///work/inputs/input.yaml"]


def test_owner_option_overrides_uploaded_by():
    options = ExportOptions(
        owner_group="imas", contact_email="x@iter.org", simdb_url="u", owner="admin"
    )
    assert simulation_to_dataset(_sim(PARENT_UUID, "p"), options).owner == "admin"


def test_alias_falls_back_to_uuid_and_owner_to_unknown():
    sim = _sim(PARENT_UUID, None, metadata=[])  # type: ignore[arg-type]
    dataset = simulation_to_dataset(sim, OPTIONS)
    assert dataset.name == str(PARENT_UUID)
    assert dataset.owner == "unknown"
    assert dataset.description is None


def test_source_folder_is_common_parent_of_output_files():
    sim = _sim(
        PARENT_UUID,
        "p",
        outputs=[
            _file("file:///work/run1/out/a.txt"),
            _file("file:///work/run1/log/b.txt"),
        ],
    )
    assert simulation_to_dataset(sim, OPTIONS).source_folder == "/work/run1"


def test_single_output_file_uses_its_directory():
    sim = _sim(PARENT_UUID, "p", outputs=[_file("file:///work/run1/out.nc")])
    assert simulation_to_dataset(sim, OPTIONS).source_folder == "/work/run1"


def test_parent_pids_become_input_datasets():
    dataset = simulation_to_dataset(
        _sim(CHILD_UUID, "child"), OPTIONS, parent_pids=["pid/parent"]
    )
    assert [str(p) for p in dataset.input_datasets] == ["pid/parent"]


def test_export_uploads_every_simulation_and_links_parents():
    source = FakeSource(
        [_sim(CHILD_UUID, "child", parents=[PARENT_UUID]), _sim(PARENT_UUID, "parent")]
    )
    client = QueryableFakeClient()

    report = export_simulations(source, client, OPTIONS)

    exported = _exported(client)
    assert set(exported) == {str(PARENT_UUID), str(CHILD_UUID)}
    parent_pid = str(exported[str(PARENT_UUID)].pid)
    assert [str(p) for p in exported[str(CHILD_UUID)].inputDatasets] == [parent_pid]
    assert sorted(report.exported) == sorted([str(PARENT_UUID), str(CHILD_UUID)])
    assert report.skipped == [] and report.failed == {}


def test_export_is_idempotent():
    source = FakeSource([_sim(PARENT_UUID, "parent")])
    client = QueryableFakeClient()

    export_simulations(source, client, OPTIONS)
    report = export_simulations(source, client, OPTIONS)

    assert len(client.datasets) == 1
    assert report.skipped == [str(PARENT_UUID)]
    assert report.exported == []


def test_rerun_links_child_to_parent_exported_earlier():
    client = QueryableFakeClient()
    export_simulations(FakeSource([_sim(PARENT_UUID, "parent")]), client, OPTIONS)

    export_simulations(
        FakeSource([_sim(CHILD_UUID, "child", parents=[PARENT_UUID])]), client, OPTIONS
    )

    exported = _exported(client)
    parent_pid = str(exported[str(PARENT_UUID)].pid)
    assert [str(p) for p in exported[str(CHILD_UUID)].inputDatasets] == [parent_pid]


def test_simulation_without_files_is_reported_as_failed_and_others_continue():
    source = FakeSource(
        [_sim(NO_FILES_UUID, "nofiles", outputs=[]), _sim(PARENT_UUID, "parent")]
    )
    # No inputs either, so there is no storage path to use.
    source.sims[str(NO_FILES_UUID)].inputs.root.clear()
    client = QueryableFakeClient()

    report = export_simulations(source, client, OPTIONS)

    assert report.exported == [str(PARENT_UUID)]
    assert "storage path" in report.failed[str(NO_FILES_UUID)]


def test_dry_run_uploads_nothing():
    client = QueryableFakeClient()
    report = export_simulations(
        FakeSource([_sim(PARENT_UUID, "parent")]), client, OPTIONS, dry_run=True
    )
    assert client.datasets == {}
    assert report.exported == [str(PARENT_UUID)]


def test_remote_source_reads_ids_and_full_simulations():
    from unittest import mock  # noqa: PLC0415

    from simdb.export.scicat import RemoteSource  # noqa: PLC0415

    api = mock.Mock()
    api.list_simulations.return_value = [mock.Mock(uuid=PARENT_UUID)]
    api.get_simulation_with_refs.return_value = "full"

    source = RemoteSource(api, limit=5)

    assert source.list_simulation_ids() == [str(PARENT_UUID)]
    api.list_simulations.assert_called_once_with(limit=5)
    assert source.get_simulation("x") == "full"
