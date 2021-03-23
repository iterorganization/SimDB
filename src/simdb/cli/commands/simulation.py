import click
from pathlib import Path
from typing import Optional, List, Tuple

from . import pass_config
from ...config.config import Config
from ...query import QueryType, parse_query_arg


@click.group()
def simulation():
    """Manage ingested simulations.
    """
    pass


@simulation.command("new")
@pass_config
@click.option("-a", "--alias", help="Alias of to assign to the simulation.")
@click.option("-u", "--uuid-only", "uuid", is_flag=True,
              help="Return a new UUID but do not insert the new simulation into the database.")
def simulation_new(config: Config, alias: str, uuid: str):
    """Create an empty simulation in the database which can be updated later.
    """
    from ...database import get_local_db
    from ...database.models import Simulation
    from ..manifest import Manifest

    simulation = Simulation(Manifest())
    simulation.alias = alias
    if not uuid:
        db = get_local_db(config)
        db.insert_simulation(simulation)
    click.echo(simulation.uuid)


@simulation.command("alias")
@pass_config
@click.option("-p", "--prefix", help="Prefix to use for the alias.", default='sim', show_default=True)
def simulation_alias(config: Config, prefix: str):
    """Generate a unique alias with the given PREFIX.
    """
    from ...database import get_local_db

    db = get_local_db(config)
    aliases = db.get_aliases(prefix)

    n = 1
    alias = f"{prefix}{n:03}"

    while alias in aliases:
        n += 1
        alias = f"{prefix}{n:03}"

    click.echo(alias)


@simulation.command("list")
@pass_config
@click.option("-m", "--meta-data", "meta", help="Additional meta-data field to print.", multiple=True, default=[])
def simulation_list(config: Config, meta: list):
    """List ingested simulations.
    """
    from ...database import get_local_db
    from .utils import print_simulations

    db = get_local_db(config)
    simulations = db.list_simulations()
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
@click.argument("manifest_file")
@click.option("-a", "--alias", help="Alias to give to simulation (overwrites any set in manifest).")
def simulation_ingest(config: Config, manifest_file: Path, alias: str):
    """Ingest a MANIFEST_FILE.
    """
    import urllib.parse
    from ...database import get_local_db
    from ...database.models import Simulation
    from ..manifest import Manifest

    manifest = Manifest()
    manifest.load(manifest_file)
    manifest.validate()

    simulation = Simulation(manifest)
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
def simulation_push(config: Config, remote: Optional[str], sim_id: str):
    """Push the simulation with the given SIM_ID (UUID or alias) to the REMOTE.
    """
    from ...database import get_local_db
    from ..remote_api import RemoteAPI
    import sys

    api = RemoteAPI(remote, config)
    db = get_local_db(config)
    simulation = db.get_simulation(sim_id)
    if simulation is None:
        raise click.ClickException(f"Failed to find simulation: {sim_id}")
    api.push_simulation(simulation, out_stream=sys.stdout)

    click.echo("success")


@simulation.command("query")
@pass_config
@click.argument("constraint", nargs=-1)
def simulation_query(config: Config, constraint: str):
    """Query the simulations.
    """
    if not constraint:
        raise click.ClickException("At least one constraint must be provided.")

    from ...database import get_local_db
    from .utils import print_simulations

    constraints: List[Tuple[str, str, QueryType]] = []
    for item in constraint:
        if '=' not in item:
            raise click.ClickException("Invalid constraint.")
        key, value = item.split('=')
        constraints.append((key,) + parse_query_arg(value))

    db = get_local_db(config)
    simulations = db.query_meta(constraints)
    print_simulations(simulations, verbose=config.verbose)


@simulation.command("validate", cls=CustomCommand)
@pass_config
@click.argument("remote", required=False)
@click.argument("sim_id")
def simulation_validate(config: Config, remote: Optional[str], sim_id: str):
    """Validate the ingested simulation with given SIM_ID (UUID or alias) using validation schema from REMOTE.
    """
    from itertools import chain
    from ...database import get_local_db
    from ...validation import ValidationError, Validator
    from ..manifest import DataObject
    from ..remote_api import RemoteAPI

    db = get_local_db(config)
    simulation = db.get_simulation(sim_id)

    api = RemoteAPI(remote, config)

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
