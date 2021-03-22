import click

from ..remote_api import RemoteAPI
from . import pass_config
from .utils import print_simulations


pass_api = click.make_pass_decorator(RemoteAPI)


class CustomGroup(click.Group):
    def parse_args(self, ctx, args):
        if args and args[0] in self.commands:
            args.insert(0, '')
        super().parse_args(ctx, args)


@click.group(cls=CustomGroup)
@click.pass_context
@pass_config
@click.argument("name", required=False)
def remote(config, ctx, name):
    """Interact with the remote SimDB service."""
    ctx.obj = RemoteAPI(name, config)


@remote.group()
def watcher():
    """Manage simulaiton watchers on REMOTE SimDB server."""
    pass


@watcher.command("list")
@pass_api
@click.argument("sim_id")
def list_watchers(api, sim_id):
    """List watchers for simulation with given SIM_ID (UUID or alias)."""
    watchers = api.list_watchers(sim_id)
    if watchers:
        click.echo(f"Watchers for simulation {sim_id}:")
        for watcher in api.list_watchers(sim_id):
            click.echo(watcher)
    else:
        click.echo(f"no watchers found for simulation {sim_id}")


@watcher.command("remove")
@pass_api
@pass_config
@click.argument("sim_id")
@click.option("-u", "--user", help="Name of the user to remove as a watcher.")
def remove_watcher(config, api, sim_id, user):
    """Remove a user from list of watchers on a simulation with given SIM_ID (UUID or alias)."""
    if not user:
        user = config.get_option("user.name")
    if not user:
        raise click.ClickException("User not provided and user.name not found in config.")
    api.remove_watcher(sim_id, user)
    click.echo(f"Watcher successfully removed for simulation {sim_id}")


@watcher.command("add")
@pass_api
@pass_config
@click.argument("sim_id")
@click.option("-u", "--user", help="Name of the user to add as a watcher.")
@click.option("-e", "--email", help="Email of the user to add as a watcher.")
@click.option("-n", "--notification",
              type=click.Choice(["Validation", "Revision", "Obsolescence", "All"], case_sensitive=False),
              default="All", show_default=True)
def add_watcher(config, api, sim_id, user, email, notification):
    """Register a user as a watcher for a simulation with given SIM_ID (UUID or alias)."""
    if not user:
        user = config.get_option("user.name")
    if not user:
        raise click.ClickException("User not provided and user.name not found in config.")
    if not email:
        email = config.get_option("user.email")
    if not user:
        raise click.ClickException("Email not provided and user.email not found in config.")
    api.add_watcher(sim_id, user, email, notification)
    click.echo(f"Watcher successfully added for simulation {sim_id}")


@remote.command("list")
@pass_api
@pass_config
@click.option("-m", "--meta-data", "meta", help="Additional meta-data field to print.", multiple=True, default=[])
def remote_list(config, api, meta):
    """List simulation available on remote."""
    simulations = api.list_simulations()
    print_simulations(simulations, verbose=config.verbose, metadata_names=meta)


@remote.command("info")
@pass_api
@click.argument("sim_id")
def remote_info(api, sim_id):
    """Print information about simulation with given SIM_ID (UUID or alias) from remote."""
    simulation = api.get_simulation(sim_id)
    click.echo(str(simulation))


@remote.command("query")
@pass_api
@pass_config
@click.argument("constraint", nargs=-1)
@click.option("-m", "--meta-data", "meta", help="Additional meta-data field to print.", multiple=True, default=[])
def remote_query(config, api, constraint, meta):
    """Perform a metadata query to find matching simulation from remote."""
    simulations = api.query_simulations(constraint)
    print_simulations(simulations, verbose=config.verbose, metadata_names=meta)


@remote.command("publish")
@pass_api
@click.argument("sim_id")
def remote_publish(api, sim_id):
    """Mark remote simulation as published."""
    api.publish_simulation(sim_id)
    click.echo("success")


@remote.command("delete")
@pass_api
@click.argument("sim_id")
def remote_delete(api, sim_id):
    """Delete specified remote simulations."""
    result = api.delete_simulation(sim_id)
    click.echo("deleted simulation: " + result["deleted"]["simulation"])
    if result["deleted"]["files"]:
        for file in result["deleted"]["files"]:
            click.echo(f"              file: {file}")


@remote.command("database")
@pass_api
def remote_database(api):
    """Reset remote database."""
    api.reset_database()
    click.echo("success")
