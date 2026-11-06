import importlib.util
from datetime import datetime, timezone
from typing import Dict, List
from uuid import UUID

import pytest

from simdb.export.scicat import (
    ExportOptions,
    export_simulations,
    simulation_to_dataset,
)
from simdb.remote.models import SimulationDataResponse

has_scitacean = importlib.util.find_spec("scitacean") is not None
if has_scitacean:
    from scitacean import Profile
    from scitacean.testing.client import FakeClient
else:
    FakeClient = object

requires_scitacean = pytest.mark.skipif(
    not has_scitacean, reason="requires scitacean library"
)

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
        self.fetched: List[str] = []

    def list_simulation_ids(self) -> List[str]:
        return list(self.sims)

    def get_simulation(self, sim_id: str) -> SimulationDataResponse:
        self.fetched.append(sim_id)
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
        self.queries = 0

        def query_datasets(fields, **_kwargs):
            self.queries += 1
            wanted = set(fields["keywords"])
            return [d for d in datasets.values() if wanted <= set(d.keywords or [])]

        scicat.query_datasets = query_datasets  # type: ignore[method-assign]


def _exported(client) -> Dict[str, object]:
    return {d.scientificMetadata["simdb"]["uuid"]: d for d in client.datasets.values()}


@requires_scitacean
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


@requires_scitacean
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


@requires_scitacean
def test_owner_option_overrides_uploaded_by():
    options = ExportOptions(
        owner_group="imas", contact_email="x@iter.org", simdb_url="u", owner="admin"
    )
    assert simulation_to_dataset(_sim(PARENT_UUID, "p"), options).owner == "admin"


@requires_scitacean
def test_alias_falls_back_to_uuid_and_owner_to_unknown():
    sim = _sim(PARENT_UUID, None, metadata=[])  # type: ignore[arg-type]
    dataset = simulation_to_dataset(sim, OPTIONS)
    assert dataset.name == str(PARENT_UUID)
    assert dataset.owner == "unknown"
    assert dataset.description is None


@requires_scitacean
@pytest.mark.parametrize(
    ("outputs", "expected"),
    [
        # Several files: their deepest common directory.
        (
            [
                _file("file:///work/run1/out/a.txt"),
                _file("file:///work/run1/log/b.txt"),
            ],
            "/work/run1",
        ),
        # One file: its directory.
        ([_file("file:///work/run1/out.nc")], "/work/run1"),
        # Legacy IMAS URI (no path=): ignored, falls back to the inputs.
        (
            [_file("imas:?user=jdoe&database=ITER&shot=1&run=2", "IMAS")],
            "/work/inputs",
        ),
    ],
    ids=["common-parent", "single-file", "legacy-imas-uri"],
)
def test_source_folder(outputs, expected):
    sim = _sim(PARENT_UUID, "p", outputs=outputs)
    assert simulation_to_dataset(sim, OPTIONS).source_folder == expected


@requires_scitacean
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


@requires_scitacean
def test_export_is_idempotent():
    source = FakeSource([_sim(PARENT_UUID, "parent")])
    client = QueryableFakeClient()

    export_simulations(source, client, OPTIONS)
    source.fetched.clear()
    client.queries = 0
    report = export_simulations(source, client, OPTIONS)

    assert len(client.datasets) == 1
    assert report.skipped == [str(PARENT_UUID)]
    assert report.exported == []
    # Already-exported simulations are skipped before fetching their details,
    # and SciCat is searched once per run, not once per simulation.
    assert source.fetched == []
    assert client.queries == 1


@requires_scitacean
def test_rerun_links_child_to_parent_exported_earlier():
    client = QueryableFakeClient()
    export_simulations(FakeSource([_sim(PARENT_UUID, "parent")]), client, OPTIONS)

    export_simulations(
        FakeSource([_sim(CHILD_UUID, "child", parents=[PARENT_UUID])]), client, OPTIONS
    )

    exported = _exported(client)
    parent_pid = str(exported[str(PARENT_UUID)].pid)
    assert [str(p) for p in exported[str(CHILD_UUID)].inputDatasets] == [parent_pid]


@requires_scitacean
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


@requires_scitacean
def test_dry_run_uploads_nothing():
    client = QueryableFakeClient()
    report = export_simulations(
        FakeSource([_sim(PARENT_UUID, "parent")]), client, OPTIONS, dry_run=True
    )
    assert client.datasets == {}
    assert report.exported == [str(PARENT_UUID)]
