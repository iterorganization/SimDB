import click

from ..remote_api import RemoteAPI
from . import pass_config
from .utils import print_simulations


pass_api = click.make_pass_decorator(RemoteAPI)


class RemoteGroup(click.Group):
    def parse_args(self, ctx, args):
        if args and args[0] in self.commands:
            args.insert(0, '')
        super().parse_args(ctx, args)


class RemoteSubGroup(click.Group):
    def format_usage(self, ctx, formatter):
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(ctx.command_path.replace('remote', 'remote [NAME]'), " ".join(pieces))


class RemoteSubCommand(click.Command):
    def format_usage(self, ctx, formatter):
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(ctx.command_path.replace('remote', 'remote [NAME]'), " ".join(pieces))


@click.group(cls=RemoteGroup)
@click.pass_context
@pass_config
@click.argument("name", required=False)
def remote(config, ctx, name):
    """Interact with the remote SimDB service.

    If NAME is provided this determines which remote server to communicate with, otherwise the server in the config file
    with default=True is used."""
    if '--help' not in click.get_os_args():
        ctx.obj = RemoteAPI(name, config)


@remote.group(cls=RemoteSubGroup)
def watcher():
    """Manage simulation watchers on REMOTE SimDB server."""
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


@remote.command("list", cls=RemoteSubCommand)
@pass_api
@pass_config
@click.option("-m", "--meta-data", "meta", help="Additional meta-data field to print.", multiple=True, default=[])
def remote_list(config, api, meta):
    """List simulations available on remote."""
    simulations = api.list_simulations()
    print_simulations(simulations, verbose=config.verbose, metadata_names=meta)


@remote.command("info", cls=RemoteSubCommand)
@pass_api
@click.argument("sim_id")
def remote_info(api, sim_id):
    """Print information about simulation with given SIM_ID (UUID or alias) from remote."""
    simulation = api.get_simulation(sim_id)
    click.echo(str(simulation))


@remote.command("query", cls=RemoteSubCommand)
@pass_api
@pass_config
@click.argument("constraint", nargs=-1)
@click.option("-m", "--meta-data", "meta", help="Additional meta-data field to print.", multiple=True, default=[])
def remote_query(config, api, constraint, meta):
    """Perform a metadata query to find matching simulation from remote."""
    simulations = api.query_simulations(constraint)
    print_simulations(simulations, verbose=config.verbose, metadata_names=meta)


@remote.command("update", cls=RemoteSubCommand)
@pass_api
@click.argument("sim_id")
@click.argument("update_type", type=click.Choice(['validate', 'accept'], case_sensitive=False))
def remote_publish(api, sim_id, update_type):
    """Mark remote simulation as published."""
    from ...database.models import Simulation
    if update_type == "accept":
        # Check if simulation is validated.
        # Error if not validated.
        # Send status updated.
        status = Simulation.Status.ACCEPTED
        api.update_simulation(sim_id, status)
    elif update_type == "validate":
        pass
    elif update_type == "deprecate":
        api.update_simulation(sim_id, Simulation.Status.DEPRECATED)
        click.echo("Simulation deprecated.")
    elif update_type == "delete":
        result = api.delete_simulation(sim_id)
        click.echo(f"deleted simulation: {result['deleted']['simulation']}")
        if result["deleted"]["files"]:
            for file in result["deleted"]["files"]:
                click.echo(f"              file: {file}")
    api.publish_simulation(sim_id)
    click.echo("success")
