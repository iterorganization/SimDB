import datetime
from typing import Annotated, Optional

from flask_restx import Namespace, Resource

from simdb.database.models import metadata as models_meta
from simdb.database.models import simulation as models_sim
from simdb.database.models import watcher as models_watcher
from simdb.enums import IngestionStatus
from simdb.remote.apis.v1_2.simulations import (
    Simulation,
    SimulationMeta,
    SimulationPackage,
    SimulationTrace,
    ValidateSimulation,
)
from simdb.remote.apis.v1_2.simulations import SimulationList as SimulationListV12
from simdb.remote.core.auth import User, requires_auth
from simdb.remote.core.cache import clear_cache
from simdb.remote.core.pydantic_utils import (
    Body,
    ResponseException,
    ServerException,
    pydantic_validate,
)
from simdb.remote.core.typing import current_app
from simdb.remote.models import (
    FileDataList,
    SimulationPostData,
    SimulationPostResponse,
    SimulationStatusResponse,
)
from simdb.validation import ValidationError
from simdb.workers.tasks import (
    complete_ingestion_task,
    copy_files_task,
    validate_imas_task,
)

api = Namespace("simulations", path="/")

api.route("/simulation/<path:sim_id>")(Simulation)
api.route("/simulation/metadata/<path:sim_id>")(SimulationMeta)
api.route("/validate/<string:sim_id>")(ValidateSimulation)
api.route("/trace/<path:sim_id>")(SimulationTrace)
api.route("/simulation/package/<path:sim_id>")(SimulationPackage)


def _set_alias(simulation: models_sim.Simulation, alias: Optional[str]):
    if alias is None:
        simulation.alias = simulation.uuid.hex
        return

    character = None
    if alias.endswith("-"):
        character = "-"
    elif alias.endswith("#"):
        character = "#"

    if not character:
        simulation.alias = alias
        return

    aliases = current_app.db.get_aliases(alias)
    last_id = max(
        (int(existing_alias.split(character)[-1]) for existing_alias in aliases),
        default=0,
    )
    next_id = last_id + 1
    simulation.alias = f"{alias}{next_id}"
    simulation.meta.append(models_meta.MetaData("seqid", next_id))


@api.route("/simulations")
class SimulationList(SimulationListV12):
    # GET is inherited unchanged from v1.2; POST is replaced with
    # asynchronous Celery-based ingestion.
    @requires_auth()
    @pydantic_validate(api)
    def post(
        self,
        user: User,
        body: Annotated[SimulationPostData, Body()],
    ) -> SimulationPostResponse:
        """Register a simulation and ingest its files in the background.

        The files are copied by a Celery worker from the given partition URIs.
        When the server validates uploads automatically the worker then runs
        the metadata and file validators; with ``validation.error_on_fail`` a
        failed validation stops the ingestion in the VALIDATION_FAILED state.
        Poll the status endpoint to follow the ingestion.
        """
        config = current_app.simdb_config
        auto_validate = config.get_option("validation.auto_validate", default=False)
        if config.get_option("validation.error_on_fail", default=False) and (
            not auto_validate
        ):
            raise ResponseException(
                "Validation config option error_on_fail=True without "
                "auto_validate=True."
            )

        simulation_data = body.model_copy(deep=True)

        # Clear the file inputs and outputs.
        # The files will be added by the job.
        simulation_data.simulation.outputs = FileDataList()
        simulation_data.simulation.inputs = FileDataList()
        simulation = models_sim.Simulation.from_data_model(simulation_data.simulation)

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

        _set_alias(simulation, body.simulation.alias)

        simulation.ingestion_status = IngestionStatus.QUEUED
        current_app.db.insert_simulation(simulation)

        # This job will copy and add the files to the simulation
        copy_files = copy_files_task.si(
            simulation.uuid,
            body.simulation.inputs.model_dump(),
            body.simulation.outputs.model_dump(),
        )

        # The complete job will set simulation.ingestion_status = Completed
        complete = complete_ingestion_task.si(simulation.uuid)

        if auto_validate:
            # Validate once the files are in place, as v1.2 does on upload.
            validate = validate_imas_task.si(simulation.uuid)
            chain = copy_files | validate | complete
        else:
            chain = copy_files | complete

        try:
            _ = chain.apply_async()
        except ValidationError as err:
            # Only reachable when the tasks run in-process (task_always_eager):
            # the validation task has recorded the failure, answer as v1.2 does.
            clear_cache()
            raise ResponseException(
                f"Simulation validation failed and server has "
                f"error_on_fail=True.\n{err}"
            ) from err
        except Exception as err:
            if not simulation.ingestion_status.is_terminal():
                simulation.ingestion_status = IngestionStatus.COPY_FAILED
                simulation.ingestion_error = f"Failed to queue ingestion: {err}"
            current_app.db.session.commit()
            clear_cache()
            raise ServerException(
                f"Failed to queue ingestion for simulation {simulation.uuid.hex}: "
                f"{err}",
                return_code=503,
            ) from err

        result = SimulationPostResponse(ingested=simulation.uuid)

        clear_cache()

        return result


@api.route("/simulation/status/<path:sim_id>")
class SimulationIngestionStatus(Resource):
    @requires_auth()
    @pydantic_validate(api)
    def get(
        self,
        sim_id: str,
        user: User,
    ) -> SimulationStatusResponse:
        """Report how far the ingestion of a simulation has progressed.

        Includes the reason when the ingestion has failed.
        """
        simulation = current_app.db.get_simulation(sim_id)
        return SimulationStatusResponse(
            status=simulation.ingestion_status, error=simulation.ingestion_error
        )
