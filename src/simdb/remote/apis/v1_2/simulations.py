import datetime
import itertools
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from flask import jsonify, request, send_file
from flask_restx import Namespace, Resource

from ....database import DatabaseError
from ....database.models import metadata as models_meta
from ....database.models import simulation as models_sim
from ....database.models import watcher as models_watcher
from ....uri import URI
from ....cli.manifest import DataObject
from ...core.typing import current_app
from ...core.alias import create_alias_dir
from ...core.auth import User, requires_auth
from ...core.cache import cache, cache_key, clear_cache
from ...core.errors import error
from ...core.path import secure_path

api = Namespace("simulations", path="/")


def _update_simulation_status(
    simulation: models_sim.Simulation, status: models_sim.Simulation.Status, user
) -> None:
    from ....email.server import EmailServer

    old_status = simulation.status
    simulation.status = status
    simulation.set_meta(
        status.value.lower().replace(" ", "_") + "_on",
        datetime.datetime.now().isoformat(),
    )
    if status != old_status and simulation.watchers.count():
        server = EmailServer(current_app.simdb_config)
        msg = f"""\
Simulation status changed from {old_status} to {status}.

Updated by {user}.

Note: please don't reply to this email, replies to this address are not monitored.
"""
        to_addresses = [w.email for w in simulation.watchers]
        if to_addresses:
            server.send_message(f"Simulation {simulation.alias}", msg, to_addresses)


def _validate(simulation, user) -> Dict:
    from ....validation import ValidationError, Validator
    from ....validation.file import find_file_validator
    from ids_validator.validate_options import ValidateOptions

    schemas = Validator.validation_schemas(current_app.simdb_config, simulation)
    try:
        for schema in schemas:
            Validator(schema).validate(simulation)
            _update_simulation_status(
                simulation, models_sim.Simulation.Status.PASSED, user
            )
    except ValidationError as err:
        _update_simulation_status(simulation, models_sim.Simulation.Status.FAILED, user)
        return {
            "passed": False,
            "error": str(err),
        }
    file_validator_type = current_app.simdb_config.get_option("ids_validation.type", default=None)
    file_validator_options = current_app.simdb_config.get_section("ids_validation", default={})
    validator_type, validator_options  = find_file_validator(file_validator_type, file_validator_options)
    if validator_type:
        for output in simulation.outputs:
            try:
                validator_type.validate_uri(output.uri, validator_options)
            except ValidationError as err:
                _update_simulation_status(simulation, models_sim.Simulation.Status.FAILED, user)
                return {
                    "passed": False,
                    "error": str(err),
                }
    else:
        error("Invalid file validator specified in configuration")

    return {
        "passed": True,
    }


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
    alias = "%s%d" % (alias, next_id)

    return alias, next_id


def _build_trace(sim_id: str) -> dict:
    try:
        simulation = current_app.db.get_simulation(sim_id)
    except DatabaseError as err:
        return {"error": str(err)}
    data = simulation.data(recurse=False)

    status = simulation.find_meta("status")
    if status:
        status = status[0].value
        if isinstance(status, str):
            data["status"] = status
        else:
            data["status"] = status.value
        status_on_name = data["status"] + "_on"
        status_on = simulation.find_meta(status_on_name)
        if status_on:
            data[status_on_name] = status_on[0].value

    replaces = simulation.find_meta("replaces")
    if replaces:
        data["replaces"] = _build_trace(replaces[0].value)

    replaced_on = simulation.find_meta("replaced_on")
    if replaced_on:
        data["deprecated_on"] = replaced_on[0].value

    replaces_reason = simulation.find_meta("replaces_reason")
    if replaces_reason:
        data["replaces_reason"] = replaces_reason[0].value

    return data


@api.route("/simulations")
class SimulationList(Resource):
    LIMIT_HEADER = "simdb-result-limit"
    PAGE_HEADER = "simdb-page"
    SORT_BY_HEADER = "simdb-sort-by"
    SORT_ASC_HEADER = "simdb-sort-asc"

    parser = api.parser()
    parser.add_argument(
        LIMIT_HEADER, location="headers", type=int, help="Limit returned results"
    )
    parser.add_argument(
        PAGE_HEADER,
        location="headers",
        type=int,
        help="Specify the page of results to return",
    )
    parser.add_argument(
        SORT_BY_HEADER,
        location="headers",
        type=str,
        help="Specify the field to sort the results by",
    )
    parser.add_argument(
        SORT_ASC_HEADER,
        location="headers",
        type=bool,
        help="Specify if the results are sorted ascending or descending",
    )

    @api.expect(parser)
    @api.response(200, "Success")
    @api.response(401, "Unauthorized")
    @requires_auth()
    # @cache.cached(key_prefix=cache_key)
    def get(self, user: User):
        from ....query import QueryType, parse_query_arg

        limit = int(request.headers.get(SimulationList.LIMIT_HEADER, 100))
        page = int(request.headers.get(SimulationList.PAGE_HEADER, 1))
        sort_by = request.headers.get(SimulationList.SORT_BY_HEADER, "")
        sort_asc = (
            request.headers.get(SimulationList.SORT_ASC_HEADER, "false").lower()
            == "true"
        )
        names = []
        constraints = []
        if request.args:
            constraints: List[Tuple[str, str, QueryType]] = []
            for name in request.args:
                if name not in ("alias", "uuid"):
                    names.append(name)
                values = request.args.getlist(name)
                for value in values:
                    constraint = parse_query_arg(value)
                    if constraint[0]:
                        constraints.append((name,) + constraint)

        if constraints:
            count, data = current_app.db.query_meta_data(
                constraints,
                names,
                limit=limit,
                page=page,
                sort_by=sort_by,
                sort_asc=sort_asc,
            )
        else:
            count, data = current_app.db.list_simulation_data(
                meta_keys=names,
                limit=limit,
                page=page,
                sort_by=sort_by,
                sort_asc=sort_asc,
            )

        return jsonify({"count": count, "page": page, "limit": limit, "results": data})

    @requires_auth()
    def post(self, user: User):
        try:
            data = request.get_json()

            if "simulation" not in data:
                return error("Simulation data not provided")

            add_watcher = data.get("add_watcher", True)

            simulation = models_sim.Simulation.from_data(data["simulation"])
            simulation.set_meta("uploaded_by", user.name)

            if add_watcher:
                simulation.watchers.append(
                    models_watcher.Watcher(
                        user.name, user.email, models_watcher.Notification.ALL
                    )
                )

            if "alias" in data["simulation"]:
                alias = data["simulation"]["alias"]
                (updated_alias, next_id) = _set_alias(alias)
                if updated_alias:
                    simulation.meta.append(models_meta.MetaData("seqid", next_id))
                    simulation.alias = updated_alias
                else:
                    simulation.alias = alias
            else:
                simulation.alias = simulation.uuid.hex[0:8]

            files = list(itertools.chain(simulation.inputs, simulation.outputs))
            sim_file_paths = set(
                f.uri.path
                for f in itertools.chain(simulation.inputs, simulation.outputs)
                if f.type == DataObject.Type.FILE
            )
            common_root = (
                Path(os.path.commonpath(sim_file_paths))
                if len(sim_file_paths) > 1
                else None
            )

            config = current_app.simdb_config

            if config.get_option("server.copy_files", default=True):
                staging_dir = (
                    Path(config.get_option("server.upload_folder"))
                    / simulation.uuid.hex
                )

                for sim_file in files:
                    if sim_file.uri.scheme == "file":
                        path = secure_path(sim_file.uri.path, common_root, staging_dir)
                        if not path.exists():
                            raise ValueError(
                                "simulation file %s not uploaded" % sim_file.uuid
                            )
                        sim_file.uri = URI(scheme="file", path=path)
                    elif sim_file.uri.scheme == "imas":
                        from simdb.imas.utils import convert_uri

                        path = secure_path(
                            Path(sim_file.uri.query["path"]), common_root, staging_dir
                        )
                        sim_file.uri = convert_uri(sim_file.uri, path, config)
            elif config.get_option("server.imas_remote_host", default=None):
                staging_dir = (
                    Path(config.get_option("server.upload_folder"))
                    / simulation.uuid.hex
                )

                for sim_file in files:
                    if sim_file.uri.scheme == "imas":
                        from simdb.imas.utils import convert_uri

                        path = secure_path(
                            Path(sim_file.uri.query["path"]), common_root, staging_dir
                        )
                        sim_file.uri = convert_uri(sim_file.uri, path, config)

            result = {
                "ingested": simulation.uuid.hex,
            }

            if current_app.simdb_config.get_option(
                "validation.auto_validate", default=False
            ):
                result["validation"] = _validate(simulation, user)

            if current_app.simdb_config.get_option(
                "validation.error_on_fail", default=False
            ):
                if simulation.status == models_sim.Simulation.Status.NOT_VALIDATED:
                    raise Exception(
                        "Validation config option error_on_fail=True without auto_validate=True."
                    )
                elif simulation.status == models_sim.Simulation.Status.FAILED:
                    result[
                        "error"
                    ] = "Simulation validation failed and server has error_on_fail=True."
                    response = jsonify(result)
                    response.status_code = 400
                    return response

            replaces = simulation.find_meta("replaces")
            if not current_app.simdb_config.get_option(
                "development.disable_replaces", default=False
            ):
                if replaces and replaces[0].value:
                    sim_id = replaces[0].value
                    try:
                        replaces_sim = current_app.db.get_simulation(sim_id)
                    except DatabaseError:
                        replaces_sim = None
                    if replaces_sim is None:
                        pass
                        # raise ValueError(f'Simulation replaces:{sim_id} is not a valid simulation identifier.')
                    else:
                        _update_simulation_status(
                            replaces_sim, models_sim.Simulation.Status.DEPRECATED, user
                        )
                        replaces_sim.set_meta("replaced_by", simulation.uuid)
                        current_app.db.insert_simulation(replaces_sim)

            current_app.db.insert_simulation(simulation)
            clear_cache()

            try:
                create_alias_dir(simulation)
            except OSError:
                pass

            return jsonify(result)
        except (DatabaseError, ValueError) as err:
            return error(str(err))


@api.route("/simulation/<path:sim_id>")
class Simulation(Resource):
    @requires_auth()
    @cache.cached(key_prefix=cache_key)
    def get(self, sim_id: str, user: User):
        try:
            simulation = current_app.db.get_simulation(sim_id)
            if simulation:
                sim_data = simulation.data(recurse=True)
                sim_data["children"] = current_app.db.get_simulation_children(
                    simulation
                )
                sim_data["parents"] = current_app.db.get_simulation_parents(simulation)
                return jsonify(sim_data)
            return error("Simulation not found")
        except DatabaseError as err:
            return error(str(err))

    parser = api.parser()
    parser.add_argument(
        'status', type=str, location="json", help = "status", required=True
    )
    @api.expect(parser)
    @requires_auth("admin")
    def patch(self, sim_id: str, user: User = Optional[None]):
        try:
            data = request.get_json()
            if "status" not in data:
                return error("Status not provided")
            simulation = current_app.db.get_simulation(sim_id)
            if simulation is None:
                raise ValueError(f"Simulation {sim_id} not found.")
            status = models_sim.Simulation.Status(data["status"])
            _update_simulation_status(simulation, status, user)
            current_app.db.insert_simulation(simulation)
            clear_cache()
            return {}
        except DatabaseError as err:
            return error(str(err))

    @requires_auth("admin")
    def delete(self, sim_id: str, user: User):
        try:
            simulation = current_app.db.delete_simulation(sim_id)
            clear_cache()
            files = []
            for file in itertools.chain(simulation.inputs, simulation.outputs):
                if file.uri.scheme == "file":
                    files.append("%s (%s)" % (file.uuid, file.uri.path.name))
                    os.remove(file.uri.path)
            if simulation.inputs or simulation.outputs:
                directory = (
                    simulation.inputs[0].uri.path.parent
                    if simulation.inputs
                    else simulation.outputs[0].uri.path.parent
                )
                if directory != Path() and directory != Path("/"):
                    os.rmdir(directory)
            return jsonify({"deleted": {"simulation": simulation.uuid, "files": files}})
        except DatabaseError as err:
            return error(str(err))


@api.route("/simulation/metadata/<path:sim_id>")
class SimulationMeta(Resource):
    @requires_auth()
    @cache.cached(key_prefix=cache_key)
    def get(self, sim_id: str, user: User):
        try:
            simulation = current_app.db.get_simulation(sim_id)
            if simulation:
                return jsonify([meta.data() for meta in simulation.meta])
            return error("Simulation not found")
        except DatabaseError as err:
            return error(str(err))

    parser = api.parser()
    parser.add_argument(
        'key', type=str, location="json", help = "status", required=True
    )
    parser.add_argument(
        'value', type=str, location="json", help = "status", required=True
    )
    @api.expect(parser)
    @requires_auth("admin")
    def patch(self, sim_id: str, user: User = Optional[None]):
        try:
            data = request.get_json()

            if "key" not in data:
                return error("Metadata key not provided")

            if "value" not in data:
                return error("New metadata value not provided")

            key = data["key"]
            value = data["value"].lower()
            simulation = current_app.db.get_simulation(sim_id)
            if simulation is None:
                raise ValueError(f"Simulation {sim_id} not found.")
            old_values = [meta.data() for meta in simulation.find_meta(key)]
            if key.lower() != 'status':
                simulation.set_meta(key, value)
            else:
                status = models_sim.Simulation.Status(value)
                _update_simulation_status(simulation, status, user)
            current_app.db.insert_simulation(simulation)
            clear_cache()
            return old_values
        except DatabaseError as err:
            return error(str(err))

    parser_delete = api.parser()
    parser_delete.add_argument(
        'key', type=str, location="json", help = "metadata key", required=True
    )
    @api.expect(parser_delete)
    @requires_auth("admin")
    def delete(self, sim_id: str, user: User = Optional[None]):
        try:
            data = request.get_json()

            if "key" not in data:
                return error("Metadata key not provided")

            key = data["key"]

            simulation = current_app.db.get_simulation(sim_id)
            if simulation is None:
                raise ValueError(f"Simulation {sim_id} not found.")

            simulation.remove_meta(key)
            current_app.db.insert_simulation(simulation)
            clear_cache()
            return {}
        except DatabaseError as err:
            return error(str(err))


@api.route("/validate/<string:sim_id>")
class ValidateSimulation(Resource):
    @requires_auth()
    def post(self, sim_id, user: User):
        try:
            simulation = current_app.db.get_simulation(sim_id)
            result = _validate(simulation, user)
            current_app.db.insert_simulation(simulation)
            clear_cache()
            return jsonify(result)
        except DatabaseError as err:
            return error(str(err))


@api.route("/trace/<path:sim_id>")
class SimulationTrace(Resource):
    @requires_auth()
    @cache.cached(key_prefix=cache_key)
    def get(self, sim_id: str, user: User):
        try:
            data = _build_trace(sim_id)
            return jsonify(data)
        except DatabaseError as err:
            return error(str(err))


@api.route("/simulation/package/<path:sim_id>")
class SimulationPackage(Resource):
    @requires_auth()
    def get(self, sim_id: str, user: User):
        try:
            simulation = current_app.db.get_simulation(sim_id)

            if not simulation:
                return error("Simulation not found")

            staging_dir = (
                Path(current_app.simdb_config.get_option("server.upload_folder"))
                / simulation.uuid.hex
            )

            import tarfile
            from io import BytesIO

            mem_file = BytesIO()
            tar = tarfile.open(mode="w:gz", fileobj=mem_file)
            tar.add(staging_dir, arcname=simulation.uuid.hex)
            tar.close()

            mem_file.seek(0)
            return send_file(mem_file, mimetype="application/x-gzip")
        except DatabaseError as err:
            return error(str(err))
