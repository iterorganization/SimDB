import contextlib
import datetime
import itertools
import shutil
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Annotated, Optional

from flask import send_file
from flask_restx import Namespace, Resource

from simdb.database import DatabaseError
from simdb.database.models import simulation as models_sim
from simdb.database.models import watcher as models_watcher
from simdb.email.server import EmailServer
from simdb.imas.utils import SimDBUrl, convert_uri
from simdb.remote.core.alias import create_alias_dir
from simdb.remote.core.auth import User, requires_auth
from simdb.remote.core.cache import cache, cache_key, clear_cache
from simdb.remote.core.errors import error
from simdb.remote.core.path import find_common_root, secure_path
from simdb.remote.core.pydantic_utils import (
    Body,
    Header,
    Query,
    ResponseException,
    pydantic_validate,
)
from simdb.remote.core.typing import current_app
from simdb.remote.models import (
    DeletedSimulation,
    MetadataDataList,
    MetadataDeleteData,
    MetadataDeleteResponse,
    MetadataPatchData,
    PaginatedResponse,
    PaginationData,
    SimulationDataResponse,
    SimulationDeleteResponse,
    SimulationListItem,
    SimulationPatchResponse,
    SimulationPostData,
    SimulationPostResponse,
    SimulationQueryParams,
    SimulationTraceData,
    StatusPatchData,
    ValidationResult,
)
from simdb.validation import ValidationError, Validator
from simdb.validation.file import find_file_validator

api = Namespace("simulations", path="/")


def _update_simulation_status(
    simulation: models_sim.Simulation, status: models_sim.Simulation.Status, user
) -> None:
    old_status = simulation.status
    simulation.status = status
    if status != old_status and len(list(simulation.watchers)) > 0:
        server = EmailServer(current_app.simdb_config)
        msg = f"""\
Simulation status changed from {old_status} to {status}.

Updated by {user}.

Note: please don't reply to this email, replies to this address are not monitored.
"""
        to_addresses = [w.email for w in simulation.watchers]
        if to_addresses:
            if simulation.alias is None or simulation.alias == "":
                server.send_message(
                    f"Simulation {simulation.uuid.hex}", msg, to_addresses
                )
            else:
                server.send_message(f"Simulation {simulation.alias}", msg, to_addresses)


def _validate(simulation, user) -> ValidationResult:
    schemas = Validator.validation_schemas(current_app.simdb_config, simulation)
    try:
        for schema in schemas:
            Validator(schema).validate(simulation)
            _update_simulation_status(
                simulation, models_sim.Simulation.Status.PASSED, user
            )
    except ValidationError as err:
        _update_simulation_status(simulation, models_sim.Simulation.Status.FAILED, user)
        return ValidationResult(passed=False, error=str(err))

    file_validator_type = current_app.simdb_config.get_string_option(
        "file_validation.type", default=None
    )
    file_validator_options = current_app.simdb_config.get_section(
        "file_validation", default={}
    )
    if file_validator_type not in [None, "none", ""]:
        validator_type, validator_options = find_file_validator(
            file_validator_type, file_validator_options
        )
        if validator_type:
            for output in simulation.outputs:
                try:
                    validator_type.validate_uri(output.uri, validator_options)
                except ValidationError as err:
                    _update_simulation_status(
                        simulation, models_sim.Simulation.Status.FAILED, user
                    )
                    return ValidationResult(passed=False, error=str(err))
        else:
            error("Invalid file validator specified in configuration")

    return ValidationResult(passed=True, error=None)


def _set_alias(alias: str):
    character = None
    if alias.endswith("-"):
        character = "-"
    elif alias.endswith("#"):
        character = "#"

    if not character:
        return None, -1

    next_id = 1
    aliases = current_app.db.get_aliases(alias)
    for existing_alias in aliases:
        existing_id = int(existing_alias.split(character)[1])
        if next_id <= existing_id:
            next_id = existing_id + 1
    alias = f"{alias}{next_id}"

    return alias, next_id


def _build_trace(sim_id: str) -> SimulationTraceData:
    simulation = current_app.db.get_simulation(sim_id)
    data = simulation.to_model_trace(recurse=False)

    def get_meta_val(key, default=None):
        meta = simulation.find_meta(key)
        return meta[0] if meta else default

    status_val = get_meta_val("status")
    if status_val:
        data.status = status_val if isinstance(status_val, str) else status_val.value

        status_on_key = f"{data.status}_on"
        status_on_val = get_meta_val(status_on_key)
        if status_on_val:
            setattr(data, status_on_key, status_on_val)

    replaces_id = get_meta_val("replaces")
    if replaces_id:
        data.replaces = _build_trace(replaces_id)

    data.deprecated_on = get_meta_val("replaced_on")
    data.replaces_reason = get_meta_val("replaces_reason")

    return data


@api.route("/simulations")
class SimulationList(Resource):
    @requires_auth()
    @pydantic_validate(api)
    @api.doc(
        params={
            "<metadata_key>": {
                "description": (
                    "Any metadata key may be supplied as a query parameter to "
                    "filter on that metadata. The value is matched for equality "
                    "by default, or may use a ``comparator:value`` expression "
                    "(comparators: eq, ne, in, ni, gt, ge, lt, le, agt, age, "
                    "alt, ale, exist), e.g. ``status=passed`` or "
                    "``runtime=gt:100``. Repeat a key to apply several "
                    "constraints."
                ),
                "in": "query",
                "type": "string",
            },
        }
    )
    # @cache.cached(key_prefix=cache_key)
    def get(
        self,
        user: User,
        pagination: Annotated[PaginationData, Header()],
        filters: Annotated[SimulationQueryParams, Query()],
    ) -> PaginatedResponse[SimulationListItem]:
        """List simulations, optionally filtered by metadata.

        Returns a paginated list of simulations. Query parameters are
        interpreted as metadata constraints, so passing a metadata key and a
        query value (for example ``status=passed`` or ``runtime=gt:100``)
        filters the results to matching simulations. Values are matched for
        equality by default, or may use a ``comparator:value`` expression
        (comparators: ``eq``, ``ne``, ``in``, ``ni``, ``gt``, ``ge``, ``lt``,
        ``le``, ``agt``, ``age``, ``alt``, ``ale``, ``exist``). The special
        ``alias`` and ``uuid`` parameters filter on the simulation's identity
        rather than its metadata. Without any query parameters all simulations
        are returned. Use the pagination headers to control page size, page
        number and sorting.
        """
        names, constraints = filters.constraints()

        if constraints:
            count, data = current_app.db.query_meta_data(
                constraints,
                names,
                limit=pagination.limit,
                page=pagination.page,
                sort_by=pagination.sort_by,
                sort_asc=pagination.sort_asc,
            )
        else:
            count, data = current_app.db.list_simulation_data(
                meta_keys=names,
                limit=pagination.limit,
                page=pagination.page,
                sort_by=pagination.sort_by,
                sort_asc=pagination.sort_asc,
            )

        return PaginatedResponse[SimulationListItem].model_validate(
            {
                "count": count,
                "page": pagination.page,
                "limit": pagination.limit,
                "results": data,
            }
        )

    @requires_auth()
    @pydantic_validate(api)
    def post(
        self,
        user: User,
        body: Annotated[SimulationPostData, Body()],
    ) -> SimulationPostResponse:
        """Ingest (upload) a new simulation.

        Registers a simulation and its input and output files in the database.
        The upload timestamp and the uploading user are recorded automatically.
        If the server is configured to copy files, referenced files are moved
        from the per-simulation staging directory into permanent storage. When
        auto-validation is enabled the simulation is validated on ingest and the
        result is returned. If the simulation declares that it replaces an
        earlier one, the replaced simulation is marked deprecated. An alias may
        be requested; aliases ending in ``-`` or ``#`` are auto-numbered.
        """
        simulation = models_sim.Simulation.from_data_model(body.simulation)

        # Simulation Upload (Push) Date
        simulation.datetime = datetime.datetime.now()

        uploaded_by = body.uploaded_by or user.email or user.name or "anonymous"

        simulation.set_meta("uploaded_by", uploaded_by)

        if body.add_watcher:
            simulation.watchers.append(
                models_watcher.Watcher(
                    user.name, user.email, models_watcher.Notification.ALL
                )
            )

        alias = body.simulation.alias
        if alias is not None:
            (updated_alias, next_id) = _set_alias(alias)
            if updated_alias:
                simulation.set_meta("seqid", next_id)
                simulation.alias = updated_alias
            else:
                simulation.alias = alias
        else:
            simulation.alias = simulation.uuid.hex

        files = list(itertools.chain(simulation.inputs, simulation.outputs))
        sim_file_paths = simulation.file_paths()
        common_root = find_common_root(sim_file_paths)

        config = current_app.simdb_config
        copy_files = config.get_option("server.copy_files", default=True)
        imas_remote_host = config.get_option("server.imas_remote_host", default=None)

        if copy_files or imas_remote_host:
            staging_dir = (
                Path(config.get_string_option("server.upload_folder"))
                / simulation.uuid.hex
            )

            for sim_file in files:
                if (
                    copy_files
                    and sim_file.uri.scheme == "file"
                    and sim_file.uri.path is not None
                ):
                    path = secure_path(
                        Path(sim_file.uri.path), common_root, staging_dir
                    )
                    if not path.exists():
                        raise ResponseException(
                            f"simulation file {sim_file.uuid} not uploaded"
                        )
                    sim_file.uri = SimDBUrl.build(scheme="file", path=path.as_posix())
                elif sim_file.uri.scheme == "imas":
                    qs = dict(sim_file.uri.query_params())
                    if copy_files:
                        path = secure_path(
                            Path(qs["path"]),
                            common_root,
                            staging_dir,
                            is_file=common_root is not None,
                        )
                    else:
                        path = Path(qs["path"])
                    sim_file.uri = convert_uri(sim_file.uri, path, config)

        result = SimulationPostResponse(
            ingested=simulation.uuid, error=None, validation=None
        )

        error_on_fail = current_app.simdb_config.get_option(
            "validation.error_on_fail", default=False
        )

        if current_app.simdb_config.get_option(
            "validation.auto_validate", default=False
        ):
            result.validation = _validate(simulation, user)

            if not result.validation.passed and error_on_fail:
                raise ResponseException(
                    f"Simulation validation failed and server has "
                    f"error_on_fail=True.\n{result.validation.error}"
                )
        elif error_on_fail:
            raise ResponseException(
                "Validation config option error_on_fail=True without "
                "auto_validate=True."
            )

        disable_replaces = config.get_option(
            "development.disable_replaces", default=False
        )
        replaces = simulation.find_meta("replaces")

        if not disable_replaces and replaces and replaces[0]:
            sim_id = replaces[0]
            try:
                replaces_sim = current_app.db.get_simulation(sim_id)
            except DatabaseError:
                replaces_sim = None

            if replaces_sim is not None:
                _update_simulation_status(
                    replaces_sim, models_sim.Simulation.Status.DEPRECATED, user
                )
                replaces_sim.set_meta("replaced_by", simulation.uuid.hex)
                current_app.db.insert_simulation(replaces_sim)

        current_app.db.insert_simulation(simulation)
        clear_cache()

        with contextlib.suppress(OSError):
            create_alias_dir(simulation)

        return result


@api.route("/simulation/<path:sim_id>")
class Simulation(Resource):
    @requires_auth()
    @cache.cached(key_prefix=cache_key)  # type: ignore
    @pydantic_validate(api)
    def get(self, sim_id: str, user: User) -> SimulationDataResponse:
        """Retrieve a single simulation by id or alias.

        Returns the full simulation record, including its input and output
        files and metadata, together with references to its parent and child
        simulations. The ``sim_id`` path parameter accepts either a simulation
        UUID or an alias.
        """
        try:
            simulation = current_app.db.get_simulation(sim_id)
        except DatabaseError:
            raise ResponseException(
                f"Simulation with id {sim_id} could not be found"
            ) from None

        sim_data = simulation.to_model_with_refs(recurse=True)

        sim_data.children = current_app.db.get_simulation_children_ref(simulation)
        sim_data.parents = current_app.db.get_simulation_parents_ref(simulation)
        return sim_data

    @requires_auth("admin")
    @pydantic_validate(api)
    def patch(
        self,
        sim_id: str,
        user: Optional[User],
        body: Annotated[StatusPatchData, Body()],
    ) -> SimulationPatchResponse:
        """Update a simulation's status.

        Sets the simulation's status to the value given in the request body.
        If the status changes, any users watching the simulation are notified
        by email. Requires admin privileges.
        """
        simulation = current_app.db.get_simulation(sim_id)
        if simulation is None:
            raise ResponseException(f"Simulation {sim_id} not found.")
        status = models_sim.Simulation.Status(body.status)
        _update_simulation_status(simulation, status, user)
        current_app.db.insert_simulation(simulation)
        clear_cache()
        return SimulationPatchResponse()

    @requires_auth("admin")
    @pydantic_validate(api)
    def delete(self, sim_id: str, user: User) -> SimulationDeleteResponse:
        """Delete a simulation and its stored files.

        Removes the simulation from the database and deletes its staging
        directory and any alias symlink from disk. Returns the deleted
        simulation's id and the list of files that were removed. Requires admin
        privileges.
        """
        simulation = current_app.db.delete_simulation(sim_id)
        clear_cache()

        files = [str(p) for p in simulation.file_paths()]

        upload_folder = Path(
            current_app.simdb_config.get_string_option("server.upload_folder")
        )

        if simulation.alias:
            alias_path = upload_folder / "aliases" / simulation.alias
            if alias_path.is_symlink():
                alias_path.unlink()

        sim_dir = upload_folder / simulation.uuid.hex
        if sim_dir.is_dir():
            shutil.rmtree(sim_dir)

        return SimulationDeleteResponse(
            deleted=DeletedSimulation(simulation=simulation.uuid, files=files)
        )


@api.route("/simulation/metadata/<path:sim_id>")
class SimulationMeta(Resource):
    @requires_auth()
    @cache.cached(key_prefix=cache_key)  # type: ignore
    @pydantic_validate(api)
    def get(self, sim_id: str, user: User) -> MetadataDataList:
        """List a simulation's metadata.

        Returns all metadata entries (key/value pairs) attached to the
        simulation identified by ``sim_id`` (UUID or alias).
        """
        simulation = current_app.db.get_simulation(sim_id)
        if simulation:
            return MetadataDataList.model_validate(
                [meta.data() for meta in simulation.meta]
            )
        raise ResponseException("Simulation not found")

    @requires_auth("admin")
    @pydantic_validate(api)
    def patch(
        self,
        sim_id: str,
        user: Optional[User],
        body: Annotated[MetadataPatchData, Body()],
    ) -> MetadataDataList:
        """Set or update a metadata entry on a simulation.

        Writes the given metadata key/value pair to the simulation and returns
        the previous value(s) for that key. Updating the ``status`` key routes
        through the status-change logic and notifies watchers. Requires admin
        privileges.
        """
        key = body.key
        value = body.value.lower()
        simulation = current_app.db.get_simulation(sim_id)
        if simulation is None:
            raise ResponseException(f"Simulation {sim_id} not found.")
        old_values = MetadataDataList.model_validate(
            [{"element": key, "value": v} for v in simulation.find_meta(key)]
        )
        if key.lower() != "status":
            simulation.set_meta(key, value)
        else:
            status = models_sim.Simulation.Status(value)
            _update_simulation_status(simulation, status, user)

        current_app.db.insert_simulation(simulation)
        clear_cache()
        return old_values

    @requires_auth("admin")
    @pydantic_validate(api)
    def delete(
        self,
        sim_id: str,
        user: Optional[User],
        body: Annotated[MetadataDeleteData, Body()],
    ) -> MetadataDeleteResponse:
        """Remove a metadata entry from a simulation.

        Deletes the metadata key given in the request body from the simulation.
        Requires admin privileges.
        """
        simulation = current_app.db.get_simulation(sim_id)
        if simulation is None:
            raise ResponseException(f"Simulation {sim_id} not found.")

        simulation.remove_meta(body.key)
        current_app.db.insert_simulation(simulation)
        clear_cache()
        return MetadataDeleteResponse()


@api.route("/validate/<string:sim_id>")
class ValidateSimulation(Resource):
    @requires_auth()
    @pydantic_validate(api)
    def post(self, sim_id, user: User) -> ValidationResult:
        """Validate a simulation against its schemas.

        Runs the configured metadata and file validators against the simulation
        and updates its status to passed or failed accordingly. Returns whether
        validation passed along with any validation error message.
        """
        simulation = current_app.db.get_simulation(sim_id)
        result = _validate(simulation, user)
        current_app.db.insert_simulation(simulation)
        clear_cache()
        return result


@api.route("/trace/<path:sim_id>")
class SimulationTrace(Resource):
    @requires_auth()
    @cache.cached(key_prefix=cache_key)  # type: ignore
    @pydantic_validate(api)
    def get(self, sim_id: str, user: User) -> SimulationTraceData:
        """Trace a simulation's provenance chain.

        Returns the simulation's trace data, recursively resolving the chain of
        simulations it replaces so the full deprecation and replacement history
        can be followed. Includes status, status timestamps and replacement
        reasons.
        """
        return _build_trace(sim_id)


@api.route("/simulation/package/<path:sim_id>")
class SimulationPackage(Resource):
    @requires_auth()
    def get(self, sim_id: str, user: User):
        """Download a simulation's files as a gzipped tar archive.

        Packages the simulation's staging directory into a ``.tar.gz`` archive
        and streams it back as an ``application/x-gzip`` download.
        """
        try:
            simulation = current_app.db.get_simulation(sim_id)

            if not simulation:
                return error("Simulation not found")

            staging_dir = (
                Path(current_app.simdb_config.get_string_option("server.upload_folder"))
                / simulation.uuid.hex
            )

            mem_file = BytesIO()
            with tarfile.open(mode="w:gz", fileobj=mem_file) as tar:
                tar.add(staging_dir, arcname=simulation.uuid.hex)

            mem_file.seek(0)
            return send_file(mem_file, mimetype="application/x-gzip")
        except DatabaseError as err:
            return error(str(err))
