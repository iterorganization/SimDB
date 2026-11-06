"""Export SimDB simulation metadata to SciCat.

Each SimDB simulation becomes one SciCat *derived* dataset that holds metadata only:
no files are copied. SciCat assigns its own PIDs, so the SimDB UUID is kept in
``scientificMetadata.simdb.uuid`` and in the keyword ``simdb:<uuid>``. The keyword is
how a re-run finds simulations that were already exported, so running the export
twice does not create duplicates.

Requires the optional ``scicat`` extra (``pip install imas-simdb[scicat]``).
"""

import os.path
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    Sequence,
)

from pydantic import BaseModel, TypeAdapter, ValidationError

from simdb.database.models.utils import unflatten_dict
from simdb.imas.utils import SimDBUrl, is_legacy_imas_uri
from simdb.remote.models import FileData, SimulationDataResponse

try:
    from scitacean import PID, Client, Dataset

    scitacean_available = True
except ImportError:
    scitacean_available = False

if TYPE_CHECKING:
    from simdb.cli.remote_api import RemoteAPI

INSTALL_HINT = "SciCat export needs Scitacean: pip install 'imas-simdb[scicat]'"

SIMDB_KEYWORD = "simdb"
"""Keyword on every exported dataset; ``simdb:<uuid>`` identifies one simulation."""


class SimulationSource(Protocol):
    """Where the exporter reads simulations from (normally a SimDB server)."""

    def list_simulation_ids(self) -> List[str]: ...

    def get_simulation(self, sim_id: str) -> SimulationDataResponse: ...


class RemoteSource:
    """Reads simulations from a SimDB server through its REST API."""

    def __init__(self, api: "RemoteAPI", limit: int = 0):
        self._api = api
        self._limit = limit

    def list_simulation_ids(self) -> List[str]:
        sims = self._api.list_simulations(limit=self._limit)
        return [str(s.uuid) for s in sims]

    def get_simulation(self, sim_id: str) -> SimulationDataResponse:
        return self._api.get_simulation_with_refs(sim_id)


@dataclass(frozen=True)
class ExportOptions:
    """SciCat ownership and provenance fields that SimDB does not record."""

    owner_group: str
    contact_email: str
    simdb_url: str
    owner: Optional[str] = None
    """Overrides the simulation's ``uploaded_by`` metadata."""
    access_groups: Sequence[str] = ()
    source_folder_host: Optional[str] = None


@dataclass
class ExportReport:
    exported: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    """Already in SciCat from an earlier run."""
    failed: Dict[str, str] = field(default_factory=dict)
    """SimDB UUID -> error message."""


class ExportError(ValueError):
    pass


def uuid_keyword(sim_uuid: Any) -> str:
    return f"{SIMDB_KEYWORD}:{sim_uuid}"


def connect(url: str, token: str) -> "Client":
    """Log in to the SciCat API at ``url`` with an API token."""
    _require_scitacean()
    return Client.from_token(url=url, token=token)


def simulation_to_dataset(
    sim: SimulationDataResponse,
    options: ExportOptions,
    parent_pids: Iterable[str] = (),
) -> "Dataset":
    """Map one SimDB simulation to an (unsaved) SciCat derived dataset."""
    _require_scitacean()
    flat_meta = {m.element: _jsonable(m.value) for m in sim.metadata.root}
    sim_uuid = str(sim.uuid)

    scientific_meta = unflatten_dict(flat_meta)
    scientific_meta["simdb"] = {
        "uuid": sim_uuid,
        "alias": sim.alias,
        "server": options.simdb_url,
        "inputs": [f.uri for f in sim.inputs.root],
        "outputs": [f.uri for f in sim.outputs.root],
        "parents": [str(p.uuid) for p in sim.parents],
    }

    code_name = flat_meta.get("code.name")
    code_version = flat_meta.get("code.version")
    used_software = (
        [" ".join(str(p) for p in (code_name, code_version) if p)] if code_name else []
    )
    description = flat_meta.get("description")
    has_imas = any(f.type == "IMAS" for f in sim.outputs.root)

    return Dataset(
        type="derived",
        name=sim.alias or sim_uuid,
        description=description if isinstance(description, str) else None,
        owner=options.owner or str(flat_meta.get("uploaded_by") or "unknown"),
        owner_group=options.owner_group,
        access_groups=list(options.access_groups),
        contact_email=options.contact_email,
        creation_time=_as_utc(sim.datetime),
        creation_location=f"SimDB {options.simdb_url}",
        source_folder=_storage_path(sim),
        source_folder_host=options.source_folder_host,
        input_datasets=[PID.parse(p) for p in parent_pids],
        used_software=used_software,
        data_format="IMAS" if has_imas else None,
        keywords=[SIMDB_KEYWORD, uuid_keyword(sim_uuid)],
        meta=scientific_meta,
    )


def export_simulations(
    source: SimulationSource,
    client: "Client",
    options: ExportOptions,
    *,
    dry_run: bool = False,
) -> ExportReport:
    """Export every simulation from ``source`` to SciCat.

    SciCat is searched once, up front, for everything exported earlier; those
    simulations are skipped without fetching their details from SimDB. The rest are
    exported oldest first and always after their parents, so a child's
    ``inputDatasets`` can point at them. One failing simulation does not stop the
    others; see ``ExportReport.failed``.
    """
    report = ExportReport()
    # SimDB UUID -> SciCat PID, for earlier runs and (as it goes) this one.
    pids = _exported_pids(client)
    sims: List[SimulationDataResponse] = []
    for sim_id in source.list_simulation_ids():
        if sim_id in pids:
            report.skipped.append(sim_id)
            continue
        try:
            sims.append(source.get_simulation(sim_id))
        except Exception as err:  # report and continue with the rest
            report.failed[sim_id] = f"could not read from SimDB: {err}"
    for sim in _parents_first(sims):
        sim_uuid = str(sim.uuid)
        try:
            parent_pids = [
                pids[str(p.uuid)] for p in sim.parents if str(p.uuid) in pids
            ]
            dataset = simulation_to_dataset(sim, options, parent_pids)
            if dry_run:
                client.scicat.validate_dataset_model(dataset.make_upload_model())
            else:
                created = client.scicat.create_dataset_model(
                    dataset.make_upload_model()
                )
                pids[sim_uuid] = str(created.pid)
            report.exported.append(sim_uuid)
        except Exception as err:  # report and continue with the rest
            report.failed[sim_uuid] = str(err)
    return report


def _parents_first(
    sims: List[SimulationDataResponse],
) -> List[SimulationDataResponse]:
    """Oldest first, but always after any parent in the same batch."""
    by_uuid = {str(s.uuid): s for s in sims}
    ordered: List[SimulationDataResponse] = []
    visited: set = set()

    def visit(sim: SimulationDataResponse) -> None:
        key = str(sim.uuid)
        if key in visited:  # also breaks cycles
            return
        visited.add(key)
        for parent in sim.parents:
            if str(parent.uuid) in by_uuid:
                visit(by_uuid[str(parent.uuid)])
        ordered.append(sim)

    for sim in sorted(sims, key=lambda s: _as_utc(s.datetime)):
        visit(sim)
    return ordered


def _exported_pids(client: "Client") -> Dict[str, str]:
    """SimDB UUID -> SciCat PID for every dataset exported earlier, in one query."""
    prefix = uuid_keyword("")
    pids: Dict[str, str] = {}
    for dataset in client.scicat.query_datasets({"keywords": [SIMDB_KEYWORD]}):
        for keyword in dataset.keywords or []:
            if keyword.startswith(prefix):
                pids[keyword[len(prefix) :]] = str(dataset.pid)
    return pids


def _storage_path(sim: SimulationDataResponse) -> str:
    """The deepest directory containing all outputs (or inputs, if no outputs)."""
    for files in (sim.outputs.root, sim.inputs.root):
        dirs = [d for d in (_file_dir(f) for f in files) if d]
        if dirs:
            return os.path.commonpath(dirs)
    raise ExportError(
        f"Simulation {sim.uuid} has no file or IMAS path to use as storage path "
        "(legacy IMAS URIs without path= are not supported)."
    )


def _file_dir(file: FileData) -> Optional[str]:
    """Directory holding the file, or the IMAS data directory itself."""
    try:
        uri = TypeAdapter(SimDBUrl).validate_python(file.uri)
    except ValidationError:
        return None
    if uri.scheme == "file":
        return str(PurePosixPath(uri.path).parent) if uri.path else None
    # Legacy URIs (user/database/shot/run) resolve against the home directory and
    # $IMAS_HOME of the machine running the export, so they can't be trusted here.
    if uri.scheme == "imas" and not is_legacy_imas_uri(uri):
        return dict(uri.query_params())["path"]
    return None


def _require_scitacean() -> None:
    if not scitacean_available:
        raise ImportError(INSTALL_HINT)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump())
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "tolist"):  # numpy arrays and scalars
        return value.tolist()
    return value
