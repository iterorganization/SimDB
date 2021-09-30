import click
from pathlib import Path
from typing import Optional, List, Tuple

from . import pass_config
from ...config.config import Config
from ...query import QueryType, parse_query_arg
from .validators import validate_limit


@click.group()
def simulation():
    """Manage ingested simulations.
    """
    pass


# @simulation.command("new")
# @pass_config
# @click.option("-a", "--alias", help="Alias of to assign to the simulation.")
# @click.option("-u", "--uuid-only", "uuid", is_flag=True,
#               help="Return a new UUID but do not insert the new simulation into the database.")
# def simulation_new(config: Config, alias: str, uuid: str):
#     """Create an empty simulation in the database which can be updated later.
#     """
#     from ...database import get_local_db
#     from ...database.models import Simulation
#     from ..manifest import Manifest
#
#     simulation = Simulation(Manifest())
#     simulation.alias = alias
#     if not uuid:
#         db = get_local_db(config)
#         db.insert_simulation(simulation)
#     click.echo(simulation.uuid)


@simulation.command("list")
@pass_config
@click.option("-m", "--meta-data", "meta", help="Additional meta-data field to print.", multiple=True, default=[])
@click.option("-l", "--limit", help="Limit number of returned entries (use 0 for no limit).", default=100,
              show_default=True, callback=validate_limit)
def simulation_list(config: Config, meta: list, limit: int):
    """List ingested simulations.
    """
    from ...database import get_local_db
    from .utils import print_simulations

    db = get_local_db(config)
    simulations = db.list_simulations(meta_keys=meta, limit=limit)
    print_simulations(simulations, verbose=config.verbose, metadata_names=meta)


@simulation.command("modify")
@pass_config
@click.argument("sim_id")
@click.option("-a", "--alias", help="New alias.")
def simulation_modify(config: Config, sim_id: str, alias: str):
    """Modify the ingested simulation.
    """
    from ...database import get_local_db

    if alias is not None:
        db = get_local_db(config)
        simulation = db.get_simulation(sim_id)
        simulation.alias = alias
        db.session.commit()
    else:
        click.echo("nothing to do")


@simulation.command("delete")
@pass_config
@click.argument("sim_id")
def simulation_delete(config: Config, sim_id: str):
    """Delete the ingested simulation with given SIM_ID (UUID or alias).
    """
    from ...database import get_local_db

    db = get_local_db(config)
    sim = db.delete_simulation(sim_id)

    click.echo(f"Simulation {sim.uuid.hex} deleted.")


@simulation.command("info")
@pass_config
@click.argument("sim_id")
def simulation_info(config: Config, sim_id: str):
    """Print information on the simulation with given SIM_ID (UUID or alias).
    """
    from ...database import get_local_db

    db = get_local_db(config)
    simulation = db.get_simulation(sim_id)
    if simulation is None:
        raise KeyError(f"Failed to find simulation: {sim_id}.")
    click.echo(f"{simulation}")


@simulation.command("ingest")
@pass_config
@click.argument("manifest_file", type=click.Path(exists=True))
@click.option("-a", "--alias", help="Alias to give to simulation (overwrites any set in manifest).")
def simulation_ingest(config: Config, manifest_file: str, alias: str):
    """Ingest a MANIFEST_FILE.
    """
    import urllib.parse
    from ...database import get_local_db
    from ...database.models import Simulation
    from ..manifest import Manifest, InvalidAlias

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
        click.echo('warning: alias contains reserved characters')

    db = get_local_db(config)
    db.insert_simulation(simulation)
    click.echo(simulation.uuid)


class CustomCommand(click.Command):
    def parse_args(self, ctx, args):
        if len(args) == 1:
            args.insert(0, '')
        super().parse_args(ctx, args)


@simulation.command("push", cls=CustomCommand)
@pass_config
@click.argument("remote", required=False)
@click.argument("sim_id")
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
@click.option("--replaces", help="SIM_ID of simulation to deprecate and replace.")
def simulation_push(config: Config, remote: Optional[str], sim_id: str, username: Optional[str],
                    password: Optional[str], replaces: Optional[str]):
    """Push the simulation with the given SIM_ID (UUID or alias) to the REMOTE.
    """
    from ...database import get_local_db
    from ..remote_api import RemoteAPI
    import sys

    api = RemoteAPI(remote, username, password, config)
    db = get_local_db(config)
    simulation = db.get_simulation(sim_id)
    if simulation is None:
        raise click.ClickException(f"Failed to find simulation: {sim_id}")
    if replaces:
        simulation.set_meta("replaces", replaces)
    api.push_simulation(simulation, out_stream=sys.stdout)

    click.echo(f"Successfully pushed simulation {simulation.uuid}")


@simulation.command("query")
@pass_config
@click.argument("constraint", nargs=-1)
@click.option("-m", "--meta-data", "meta", help="Additional meta-data field to print.", multiple=True, default=[])
def simulation_query(config: Config, constraint: str, meta: List[str]):
    """Perform a metadata query to find matching local simulations.

    \b
    Each constraint must be in the form:
        NAME=[mod]VALUE

    \b
    Where `[mod]` is an optional query modifier. Available query modifiers are:
        eq: - This checks for equality (this is the same behaviour as not providing any modifier).
        ne: - This checks for value that do not equal.
        in: - This searches inside the value instead of looking for exact matches.
        ni: - This searches inside the value for elements that do not match.
        gt: - This checks for values greater than the given quantity.
        ge: - This checks for values greater than or equal to the given quantity.
        lt: - This checks for values less than the given quantity.
        le: - This checks for values less than or equal to the given quantity.

    \b
    Modifier examples:
        responsible_name=foo        performs exact match
        responsible_name=in:foo     matches all names containing foo
        pulse=gt:1000               matches all pulses > 1000

    \b
    Any string comparisons are done in a case-insensitive manner. If multiple constraints are provided then simulations
    are returned that match all given constraints.

    \b
    Examples:
        sim simulation query workflow.name=in:test       finds all simulations where workflow.name contains test
                                                         (case-insensitive)
        sim simulation query pulse=gt:1000 run=0         finds all simulations where pulse is > 1000 and run = 0
    """
    if not constraint:
        raise click.ClickException("At least one constraint must be provided.")

    from ...database import get_local_db
    from .utils import print_simulations

    constraints: List[Tuple[str, str, QueryType]] = []
    names = []
    for item in constraint:
        if '=' not in item:
            raise click.ClickException("Invalid constraint.")
        key, value = item.split('=')
        names.append(key)
        constraints.append((key,) + parse_query_arg(value))
    names += meta

    db = get_local_db(config)
    simulations = db.query_meta(constraints)
    print_simulations(simulations, verbose=config.verbose, metadata_names=names)


@simulation.command("validate", cls=CustomCommand)
@pass_config
@click.argument("remote", required=False)
@click.argument("sim_id")
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
def simulation_validate(config: Config, remote: Optional[str], sim_id: str, username: str, password: str):
    """Validate the ingested simulation with given SIM_ID (UUID or alias) using validation schema from REMOTE.
    """
    from itertools import chain
    from ...database import get_local_db
    from ...validation import ValidationError, Validator
    from ..manifest import DataObject
    from ..remote_api import RemoteAPI

    db = get_local_db(config)
    simulation = db.get_simulation(sim_id)

    api = RemoteAPI(remote, username, password, config)

    click.echo('downloading validation schema ... ', nl=False)
    schema = api.get_validation_schema()
    click.echo('done')

    click.echo('validating ... ', nl=False)
    Validator(schema).validate(simulation)

    for file in chain(simulation.inputs, simulation.outputs):
        if file.type == DataObject.Type.UDA:
            from ...uda.checksum import checksum as uda_checksum
            checksum = uda_checksum(file.uri)
        elif file.type == DataObject.Type.IMAS:
            from ...imas.checksum import checksum as imas_checksum
            checksum = imas_checksum(file.uri)
        elif file.type == DataObject.Type.FILE:
            from ...checksum import sha1_checksum
            checksum = sha1_checksum(file.uri)
        else:
            raise ValidationError("invalid checksum for file %s" % file.uri)

        if checksum != file.checksum:
            raise ValidationError("Checksum doest not match for file " + str(file))

    click.echo("success")
