import contextlib
import sys
import time
import urllib.parse
from itertools import chain
from pathlib import Path
from typing import Any, List, Optional, Tuple

import appdirs
import click
from rich.prompt import Confirm

from simdb.cli.manifest import Manifest
from simdb.cli.remote_api import RemoteAPI, RemoteError
from simdb.config.config import Config
from simdb.database import DatabaseError, get_local_db
from simdb.database.models import Simulation
from simdb.enums import IngestionStatus
from simdb.query import QueryType, parse_query_arg
from simdb.validation import ValidationError, Validator

from . import check_meta_args, pass_config
from .utils import (
    is_numeric_1d,
    print_quantity,
    print_simulations,
    show_quantity_textual_plot,
)
from .validators import validate_non_negative


@click.group()
def simulation():
    """Manage ingested simulations."""
    pass


@simulation.command("list")
@pass_config
@click.option(
    "-m",
    "--meta-data",
    "meta",
    help="Additional meta-data field to print.",
    multiple=True,
    default=[],
)
@click.option(
    "-l",
    "--limit",
    help="Limit number of returned entries (use 0 for no limit).",
    default=100,
    show_default=True,
    callback=validate_non_negative,
)
@click.option(
    "--uuid",
    "show_uuid",
    is_flag=True,
    help="Include UUID in the output.",
    default=False,
)
def simulation_list(config: Config, meta: List[str], limit: int, show_uuid: bool):
    """List ingested simulations."""

    check_meta_args(meta)
    db = get_local_db(config)
    simulations = db.list_simulations(meta_keys=meta, limit=limit)
    print_simulations(
        simulations, verbose=config.verbose, metadata_names=meta, show_uuid=show_uuid
    )


class NameValueOption(click.Option):
    def type_cast_value(self, ctx: click.Context, value: Any) -> Any:
        pass


@simulation.command("modify")
@pass_config
@click.argument("sim_id")
@click.option("-a", "--alias", help="New alias.", metavar="ALIAS")
@click.option(
    "--set-meta", help="Add new meta or update existing.", metavar="NAME=VALUE"
)
@click.option("--del-meta", help="Delete metadata entry.", metavar="NAME")
def simulation_modify(
    config: Config,
    sim_id: str,
    alias: Optional[str],
    set_meta: Optional[str],
    del_meta: Optional[str],
):
    """Modify the ingested simulation."""

    if alias is not None:
        db = get_local_db(config)
        simulation = db.get_simulation(sim_id)
        simulation.alias = alias
        db.session.commit()
        click.echo("alias updated")
    elif set_meta is not None:
        try:
            name, value = set_meta.split("=")
        except ValueError:
            raise click.BadParameter(
                "set-meta argument must be of form NAME=VALUE"
            ) from None
        db = get_local_db(config)
        simulation = db.get_simulation(sim_id)
        simulation.set_meta(name, value)
        db.session.commit()
        click.echo("metadata updated")
    elif del_meta is not None:
        db = get_local_db(config)
        simulation = db.get_simulation(sim_id)
        simulation.remove_meta(del_meta)
        db.session.commit()
        click.echo("metadata deleted")
    else:
        click.echo("nothing to do")


@simulation.command("delete")
@pass_config
@click.argument("sim_id", required=False)
@click.option(
    "--all",
    "delete_all",
    is_flag=True,
    help="Reset the local database, deleting all simulations.",
)
def simulation_delete(config: Config, sim_id: Optional[str], delete_all: bool):
    """Delete the ingested simulation with given SIM_ID (UUID or alias).

    Use --all to reset the local database and delete all simulations."""
    if delete_all and Confirm.ask(
        "This will delete all locally stored simulation entries, are you sure?"
    ):
        db_file = Path(
            config.get_string_option("db.file", default=None)
            or f"{appdirs.user_data_dir('simdb')}/sim.db"
        )
        db_file.unlink(missing_ok=True)
        click.echo("Local database reset.")
        return

    db = get_local_db(config)

    if sim_id is None:
        raise click.ClickException("Either SIM_ID or --all must be provided.")

    sim = db.delete_simulation(sim_id)

    click.echo(f"Simulation {sim.uuid.hex} deleted.")


@simulation.command("info")
@pass_config
@click.argument("sim_id")
def simulation_info(config: Config, sim_id: str):
    """Print information on the simulation with given SIM_ID (UUID or alias)."""

    db = get_local_db(config)
    simulation = db.get_simulation(sim_id)
    if simulation is None:
        raise KeyError(f"Failed to find simulation: {sim_id}.")
    click.echo(f"{simulation}")


@simulation.command("ingest")
@pass_config
@click.argument("manifest_file", type=click.Path(exists=True))
@click.option(
    "-a",
    "--alias",
    help="Alias to give to simulation (overwrites any set in manifest).",
)
def simulation_ingest(config: Config, manifest_file: str, alias: str):
    """Ingest a MANIFEST_FILE."""

    overrides = {}
    if alias:
        overrides["alias"] = alias

    manifest = Manifest.load_from_file(Path(manifest_file), overrides=overrides)

    simulation = Simulation(manifest, config)
    if alias:
        simulation.alias = alias

    if simulation.alias and urllib.parse.quote(simulation.alias) != simulation.alias:
        click.echo("warning: alias contains reserved characters")

    db = get_local_db(config)
    db.insert_simulation(simulation)

    if not simulation.alias and not alias:
        simulation.alias = simulation.uuid.hex
        db.session.commit()

    click.echo("ALIAS: " + simulation.alias + "\nUUID: " + str(simulation.uuid))


class OptionalRemoteCommand(click.Command):
    """A command declared as `[REMOTE] ARG...` whose REMOTE may be left out."""

    def parse_args(self, ctx, args):
        arguments = [p for p in self.get_params(ctx) if isinstance(p, click.Argument)]
        if self._count_values_given(ctx, args, arguments) < len(arguments):
            args = ["", *args]
        super().parse_args(ctx, args)

    def _count_values_given(self, ctx, args, arguments) -> int:
        """Count how many of the ARGUMENTS the command line provides a value for."""
        values = self.make_parser(ctx).parse_args(list(args))[0]
        return sum(1 for argument in arguments if values.get(argument.name) is not None)


def _prepare_simulation(
    config: Config, api: RemoteAPI, sim_id: str, replaces: Optional[str]
) -> Simulation:
    """Look up the local simulation SIM_ID and validate it against the remote
    schemas."""
    db = get_local_db(config)

    simulation = db.get_simulation(sim_id)
    if simulation is None:
        raise click.ClickException(f"Failed to find simulation: {sim_id}")

    if replaces:
        simulation.set_meta("replaces", replaces)

    schemas = api.get_validation_schemas()
    try:
        for schema in schemas:
            Validator(schema).validate(simulation)
    except ValidationError as err:
        raise click.ClickException(f"Simulation does not validate: {err}") from err

    return simulation


def _wait_for_ingestion(api: RemoteAPI, sim_id: str, timeout: float) -> IngestionStatus:
    """Poll the remote until the ingestion of SIM_ID reaches a terminal state.

    Reports every status change and returns the terminal status.

    :raise click.ClickException: if the remote cannot be reached, reports an
                                 unknown status, or TIMEOUT seconds pass before
                                 the ingestion finishes.
    """
    max_consecutive_failures = 5
    poll_interval = 1.0

    click.echo("Waiting for ingestion to complete...", nl=False)
    last_status = None
    consecutive_failures = 0
    deadline = time.monotonic() + timeout
    while True:
        try:
            status = api.get_ingestion_status(sim_id)
        except RemoteError as err:
            # The remote rejected the request, so retrying will not help.
            click.echo()
            raise click.ClickException(
                f"Failed to check ingestion status: {err}"
            ) from err
        except Exception as err:
            # Tolerate transient errors: the ingestion continues server-side
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                click.echo()
                raise click.ClickException(
                    f"Failed to check ingestion status "
                    f"{consecutive_failures} times in a row: {err}"
                ) from err
            if time.monotonic() >= deadline:
                click.echo()
                raise click.ClickException(
                    f"Timed out after {timeout:g}s waiting for ingestion to "
                    f"complete (last status: {last_status})"
                ) from err
            time.sleep(poll_interval)
            continue
        consecutive_failures = 0

        try:
            ingestion_status = IngestionStatus(status)
        except ValueError as err:
            click.echo()
            raise click.ClickException(
                f"Remote reported an unknown ingestion status: {status}"
            ) from err

        if status != last_status:
            if last_status is not None:
                click.echo(f" -> {status}", nl=False)
            else:
                click.echo(f" {status}", nl=False)
            last_status = status

        if ingestion_status.is_terminal():
            click.echo()
            return ingestion_status

        if time.monotonic() >= deadline:
            click.echo()
            raise click.ClickException(
                f"Timed out after {timeout:g}s waiting for ingestion to complete "
                f"(last status: {status})"
            )

        time.sleep(poll_interval)


@simulation.command(
    "push_local",
    cls=OptionalRemoteCommand,
    short_help="Register a simulation whose files the REMOTE copies itself.",
)
@pass_config
@click.argument("remote", required=False)
@click.argument("sim_id")
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
@click.option("--replaces", help="SIM_ID of simulation to deprecate and replace.")
@click.option(
    "--add-watcher",
    is_flag=True,
    help="Add the current user as a watcher of the simulation.",
)
@click.option(
    "--timeout",
    type=float,
    default=600.0,
    show_default=True,
    help="Maximum number of seconds to wait for ingestion to complete.",
)
def simulation_push_local(
    config: Config,
    remote: Optional[str],
    sim_id: str,
    username: Optional[str],
    password: Optional[str],
    replaces: Optional[str],
    add_watcher: bool,
    timeout: float,
):
    """Register the simulation with the given SIM_ID (UUID or alias) on the REMOTE.

    Only the metadata is sent: the REMOTE copies the simulation files itself from
    the recorded paths, which must therefore be reachable from the remote.
    Waits for the remote ingestion to reach a terminal state, or until --timeout
    seconds have passed.
    """

    api = RemoteAPI(remote, username, password, config)
    simulation = _prepare_simulation(config, api, sim_id, replaces)

    api.push_local_simulation(simulation, add_watcher=add_watcher)

    status = _wait_for_ingestion(api, simulation.uuid.hex, timeout)
    if status is not IngestionStatus.COMPLETED:
        raise click.ClickException(
            f"Simulation ingestion failed with status: {status.value}"
        )

    click.echo(f"Successfully pushed simulation {simulation.uuid}")


@simulation.command(
    "push",
    cls=OptionalRemoteCommand,
    short_help="Upload a simulation and its files to the REMOTE.",
)
@pass_config
@click.argument("remote", required=False)
@click.argument("sim_id")
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
@click.option("--replaces", help="SIM_ID of simulation to deprecate and replace.")
@click.option(
    "--add-watcher",
    is_flag=True,
    help="Add the current user as a watcher of the simulation.",
)
def simulation_push(
    config: Config,
    remote: Optional[str],
    sim_id: str,
    username: Optional[str],
    password: Optional[str],
    replaces: Optional[str],
    add_watcher: bool,
):
    """Push the simulation with the given SIM_ID (UUID or alias) to the REMOTE.

    Both the metadata and the simulation files are uploaded over HTTP. Use
    push_local instead when the REMOTE can read the files itself.
    """

    api = RemoteAPI(remote, username, password, config)
    simulation = _prepare_simulation(config, api, sim_id, replaces)

    api.push_simulation(simulation, out_stream=sys.stdout, add_watcher=add_watcher)

    click.echo(f"Successfully pushed simulation {simulation.uuid}")


@simulation.command("pull", cls=OptionalRemoteCommand)
@pass_config
@click.argument("remote", required=False)
@click.argument("sim_id")
@click.argument("directory", type=Path)
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
def simulation_pull(
    config: Config,
    remote: Optional[str],
    sim_id: str,
    directory: Path,
    username: Optional[str],
    password: Optional[str],
):
    """Pull the simulation with the given SIM_ID (UUID or alias) from the REMOTE."""

    api = RemoteAPI(remote, username, password, config)
    db = get_local_db(config)

    local_sim = None
    with contextlib.suppress(DatabaseError):
        local_sim = db.get_simulation(sim_id)

    if local_sim is not None:
        raise click.ClickException(f"Simulation with sim_id {sim_id} already exists")

    try:
        simulation = api.pull_simulation(sim_id, directory, out_stream=sys.stdout)
    except RemoteError as err:
        raise click.ClickException(str(err)) from err

    db.insert_simulation(simulation)

    click.echo(f"Successfully pulled simulation {simulation.uuid}")


@simulation.command("query")
@pass_config
@click.argument("constraints", nargs=-1)
@click.option(
    "-m",
    "--meta-data",
    "meta",
    help="Additional meta-data field to print.",
    multiple=True,
    default=[],
)
@click.option(
    "--uuid",
    "show_uuid",
    is_flag=True,
    help="Include UUID in the output.",
    default=False,
)
def simulation_query(
    config: Config, constraints: List[str], meta: List[str], show_uuid: bool
):
    """Perform a metadata query to find matching local simulations.

    \b
    Each constraint must be in the form:
        NAME=[mod]VALUE

    \b
    Where `[mod]` is an optional query modifier. Available query modifiers are:
        eq: - This checks for equality (this is the same behaviour as not providing any
              modifier).
        ne: - This checks for value that do not equal.
        in: - This searches inside the value instead of looking for exact matches.
        ni: - This searches inside the value for elements that do not match.
        gt: - This checks for values greater than the given quantity.
        ge: - This checks for values greater than or equal to the given quantity.
        lt: - This checks for values less than the given quantity.
        le: - This checks for values less than or equal to the given quantity.

    For the following modifiers, VALUE should not be provided.
        exist: - This returns simulations where metadata with NAME exists, regardless
                 of the value.

    \b
    Modifier examples:
        responsible_name=foo        performs exact match
        responsible_name=in:foo     matches all names containing foo
        pulse=gt:1000               matches all pulses > 1000
        sequence=exist:             matches all simulations that have "sequence"
                                    metadata values

    \b
    Any string comparisons are done in a case-insensitive manner. If multiple
    constraints are provided then simulations are returned that match all given
    constraints.

    \b
    Examples:
        sim simulation query workflow.name=in:test       finds all simulations where
                                                         workflow.name contains test
                                                         (case-insensitive)
        sim simulation query pulse=gt:1000 run=0         finds all simulations where
                                                         pulse is > 1000 and run = 0
    """
    if not constraints:
        raise click.ClickException("At least one constraint must be provided.")

    check_meta_args(meta)

    parsed_constraints: List[Tuple[str, str, QueryType]] = []
    names = []
    for constraint in constraints:
        if "=" not in constraint:
            raise click.ClickException(f"Invalid constraint {constraint}.")
        key, value = constraint.split("=")
        names.append(key)
        parsed_constraints.append((key, *parse_query_arg(value)))
    names += meta

    db = get_local_db(config)
    simulations = db.query_meta(parsed_constraints)
    print_simulations(
        simulations, verbose=config.verbose, metadata_names=names, show_uuid=show_uuid
    )


@simulation.command("data", cls=OptionalRemoteCommand)
@pass_config
@click.argument("remote", required=False)
@click.argument("sim_id")
@click.argument("ids_path")
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
@click.option(
    "--dd-version",
    help="Convert IDS data to the requested Data Dictionary version, e.g. 4.1.1.",
)
def simulation_data(
    config: Config,
    remote: Optional[str],
    sim_id: str,
    ids_path: str,
    username: Optional[str],
    password: Optional[str],
    dd_version: Optional[str],
):
    """Fetch IDS field data for simulation SIM_ID (UUID or alias) from REMOTE.

    \b
    IDS_PATH format:
        ids_name[:<occurrence>]/path/to/field

    \b
    Examples:
        simdb sim data iter 4dd781b... profiles_1d[0]/grid/rho_tor_norm
        simdb sim data 4dd781b... equilibrium:0/time_slice[0]/profiles_1d/psi
    """
    api = RemoteAPI(remote, username, password, config)

    try:
        result = api.get_simulation_data(sim_id, ids_path, dd_version=dd_version)
    except Exception as err:
        raise click.ClickException(str(err)) from err

    click.echo(f"simulation : {result['simulation']}")
    click.echo(f"path       : {result['path']}  (occurrence {result['occurrence']})")

    coordinates = result.get("coordinates") or []
    plot_coordinate = next(
        (
            coord
            for coord in coordinates
            if isinstance(coord.get("data"), list)
            and isinstance(result["field"].get("data"), list)
            and len(coord["data"]) == len(result["field"]["data"])
        ),
        None,
    )
    field_is_1d = is_numeric_1d(result["field"].get("data"))
    if field_is_1d:
        show_quantity_textual_plot(
            result["field"], label="field", x_quantity=plot_coordinate
        )
    else:
        print_quantity(result["field"], label="field")

    if config.verbose and coordinates:
        for coord in coordinates:
            if field_is_1d and is_numeric_1d(coord.get("data")):
                continue
            if isinstance(coord.get("data"), list):
                print_quantity(coord, label=f"coord  {coord['name']}", show_stats=False)


@simulation.command("validate", cls=OptionalRemoteCommand)
@pass_config
@click.argument("remote", required=False)
@click.argument("sim_id")
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
def simulation_validate(
    config: Config, remote: Optional[str], sim_id: str, username: str, password: str
):
    """Validate the ingested simulation with given SIM_ID (UUID or alias) using
    validation schema from REMOTE."""

    db = get_local_db(config)
    simulation = db.get_simulation(sim_id)

    api = RemoteAPI(remote, username, password, config)

    click.echo("downloading validation schema ... ", nl=False)
    schemas = api.get_validation_schemas()
    click.echo("done")

    click.echo("validating metadata ... ", nl=False)
    for schema in schemas:
        Validator(schema).validate(simulation)

    ids_list = []
    for file in chain(simulation.inputs, simulation.outputs):
        try:
            # Pass config and ids_list parameters
            current_checksum = file.generate_checksum(config, ids_list)

            if current_checksum != file.checksum:
                raise ValidationError(
                    f"Checksum mismatch for file {file.uri}. "
                    f"Expected: {file.checksum}, Got: {current_checksum}"
                )
        except Exception as e:
            raise ValidationError(
                f"Failed to validate checksum for file {file.uri}"
            ) from e

    click.echo("validation successful")
