import contextlib
import sys
import urllib.parse
from itertools import chain
from pathlib import Path
from typing import Any, List, Optional, Tuple, Type

import click

from simdb.cli.manifest import InvalidAlias, Manifest
from simdb.cli.remote_api import RemoteAPI, RemoteError
from simdb.config.config import Config
from simdb.database import DatabaseError, get_local_db
from simdb.database.models import Simulation
from simdb.query import QueryType, parse_query_arg
from simdb.validation import ValidationError, Validator

from . import check_meta_args, pass_config
from .utils import print_simulations
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
@click.argument("sim_id")
def simulation_delete(config: Config, sim_id: str):
    """Delete the ingested simulation with given SIM_ID (UUID or alias)."""

    db = get_local_db(config)
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

    manifest = Manifest()
    manifest.load(Path(manifest_file))
    try:
        manifest.validate()
    except InvalidAlias:
        if not alias:
            raise

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


def n_required_args_adaptor(n) -> Type[click.Command]:
    class NRequiredArgs(click.Command):
        NArgs = n

        def parse_args(self, ctx, args):
            if len(args) == self.NArgs:
                args.insert(0, "")
            super().parse_args(ctx, args)

    return NRequiredArgs


@simulation.command("push", cls=n_required_args_adaptor(1))
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
    """Push the simulation with the given SIM_ID (UUID or alias) to the REMOTE."""

    api = RemoteAPI(remote, username, password, config)
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
        raise click.ClickException("Simulation does not validate") from err

    api.push_simulation(simulation, out_stream=sys.stdout, add_watcher=add_watcher)

    click.echo(f"Successfully pushed simulation {simulation.uuid}")


@simulation.command("pull", cls=n_required_args_adaptor(2))
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
        raise click.ClickException() from err

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


@simulation.command("validate", cls=n_required_args_adaptor(1))
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
