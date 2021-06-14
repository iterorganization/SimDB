import re
import sys
import click
from collections.abc import Iterable
from click_option_group import optgroup, MutuallyExclusiveOptionGroup
from typing import List, TYPE_CHECKING, Optional, Tuple

from ..remote_api import RemoteAPI
from . import pass_config
from .utils import print_simulations, print_trace
from ...notifications import Notification
from .validators import validate_limit


pass_api = click.make_pass_decorator(RemoteAPI)


if TYPE_CHECKING or 'sphinx' in sys.modules:
    from ...config import Config
    from click import Context


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


def is_empty(value) -> bool:
    return any(value) if isinstance(value, Iterable) else bool(value)


@click.group(cls=RemoteGroup, invoke_without_command=True)
@click.pass_context
@pass_config
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
@optgroup.group("Remote options", cls=MutuallyExclusiveOptionGroup, help="Commands for managing remotes")
@optgroup.option("--set-default", help="Set the remote as the default.", metavar='NAME')
@optgroup.option("--get-default", is_flag=True, help="Print the currently set default remote.")
@optgroup.option("--new", type=(str, str), default=('', ''), help="Create a new default.", metavar='NAME URL')
@optgroup.option("--delete", is_flag=True, help="Delete a registered remote.")
@optgroup.option("--list", is_flag=True, help="List all registered remotes.")
@click.argument("name", required=False)
def remote(config: "Config", ctx: "Context", username: str, password: str, name: str, set_default: str,
           get_default: bool, new: Tuple[str, str], delete: bool, list: bool):
    """Interact with the remote SimDB service.

    If NAME is provided this determines which remote server to communicate with, otherwise the server in the config file
    with default=True is used.
    """
    if not ctx.invoked_subcommand and not any(is_empty(i) for i in ctx.params.values()):
        click.echo(ctx.get_help())
    elif '--help' not in click.get_os_args():
        if get_default:
            click.echo(config.default_remote)
        elif set_default:
            config.default_remote = set_default
            config.save()
        elif new[0] or new[1]:
            config.set_option(f"remote.{new[0]}.url", new[1])
            config.save()
        elif list:
            r = re.compile(r'remote\.(.*)\.url: (.*)')
            for option in config.list_options():
                m = r.match(option)
                if m:
                    click.echo(f"{m[1]}: {m[2]}" + (" (default)" if m[1] == config.default_remote else ""))
        elif delete:
            config.delete_section(f'remote.{name}')
            config.save()
        elif ctx.invoked_subcommand:
            ctx.obj = RemoteAPI(name, username, password, config)


@remote.group(cls=RemoteSubGroup)
def watcher():
    """Manage simulation watchers on REMOTE SimDB server.
    """
    pass


@watcher.command("list")
@pass_api
@click.argument("sim_id")
def list_watchers(api: RemoteAPI, sim_id: str):
    """List watchers for simulation with given SIM_ID (UUID or alias).
    """
    watchers = api.list_watchers(sim_id)
    if watchers:
        click.echo(f"Watchers for simulation {sim_id}:")
        for watcher in watchers:
            click.echo(watcher)
    else:
        click.echo(f"no watchers found for simulation {sim_id}")


@watcher.command("remove")
@pass_api
@pass_config
@click.argument("sim_id")
@click.option("-u", "--user", help="Name of the user to remove as a watcher.")
def remove_watcher(config: "Config", api: RemoteAPI, sim_id: str, user: str):
    """Remove a user from list of watchers on a simulation with given SIM_ID (UUID or alias).
    """
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
              type=click.Choice(list(i.name for i in Notification), case_sensitive=False),
              default=Notification.ALL.name, show_default=True)
def add_watcher(config: "Config", api: RemoteAPI, sim_id: str, user: Optional[str], email: Optional[str],
                notification: Optional[str]):
    """Register a user as a watcher for a simulation with given SIM_ID (UUID or alias).
    """
    if not user:
        user = config.get_option("user.name")
    if not user:
        raise click.ClickException("User not provided and user.name not found in config.")
    if not email:
        email = config.get_option("user.email")
    if not user:
        raise click.ClickException("Email not provided and user.email not found in config.")
    api.add_watcher(sim_id, user, email, getattr(Notification, notification))
    click.echo(f"Watcher successfully added for simulation {sim_id}")


@remote.command("list", cls=RemoteSubCommand)
@pass_api
@pass_config
@click.option("-m", "--meta-data", "meta", help="Additional meta-data field to print.", multiple=True, default=[],
              metavar='NAME')
@click.option("-l", "--limit", help="Limit number of returned entries (use 0 for no limit).", default=100,
              show_default=True, callback=validate_limit)
def remote_list(config: "Config", api: RemoteAPI, meta: List[str], limit: int):
    """List simulations available on remote.
    """
    simulations = api.list_simulations(meta, limit)
    print_simulations(simulations, verbose=config.verbose, metadata_names=meta)


@remote.command("info", cls=RemoteSubCommand)
@pass_api
@click.argument("sim_id")
def remote_info(api: RemoteAPI, sim_id: str):
    """Print information about simulation with given SIM_ID (UUID or alias) from remote.
    """
    simulation = api.get_simulation(sim_id)
    click.echo(str(simulation))


@remote.command("trace", cls=RemoteSubCommand)
@pass_api
@click.argument("sim_id")
def remote_trace(api: RemoteAPI, sim_id: str):
    trace_data = api.trace_simulation(sim_id)
    print_trace(trace_data)


@remote.command("query", cls=RemoteSubCommand)
@pass_api
@pass_config
@click.argument("constraints", nargs=-1)
@click.option("-m", "--meta-data", "meta", help="Additional meta-data field to print.", multiple=True, default=[])
def remote_query(config: "Config", api: RemoteAPI, constraints: List[str], meta: List[str]):
    """Perform a metadata query to find matching remote simulations.

    \b
    Each constraint must be in the form:
        NAME=[mod]VALUE

    \b
    Where `[mod]` is an optional query modifier. Available query modifiers are:
        eq: - This checks for equality (this is the same behaviour as not providing any modifier).
        in: - This searches inside the value instead of looking for exact matches.
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
        sim remote query workflow.name=in:test       finds all simulations where workflow.name contains test
                                                         (case-insensitive)
        sim remote query pulse=gt:1000 run=0         finds all simulations where pulse is > 1000 and run = 0
    """
    simulations = api.query_simulations(constraints)

    names = []
    meta = meta or []
    for constraint in constraints:
        name, _ = constraint.split('=')
        meta.append(name)
    names += meta

    print_simulations(simulations, verbose=config.verbose, metadata_names=names)


@remote.command("update", cls=RemoteSubCommand)
@pass_api
@click.argument("sim_id")
@click.argument("update_type", type=click.Choice(['validate', 'accept', 'deprecate'], case_sensitive=False))
def remote_update(api: RemoteAPI, sim_id: str, update_type: str):
    """Mark remote simulation as published.
    """
    from ...database.models import Simulation
    if update_type == "accept":
        # TODO: Check if simulation is validated.
        # TODO: Error if not validated.
        api.validate_simulation(sim_id)
        api.update_simulation(sim_id, Simulation.Status.ACCEPTED)
        click.echo(f"Simulation {sim_id} marked as accepted.")
    elif update_type == "validate":
        ok, err = api.validate_simulation(sim_id)
        if ok:
            click.echo(f"Simulation {sim_id} validated successfully.")
        else:
            click.echo(f"Validation error: {err}.")
    elif update_type == "deprecate":
        api.update_simulation(sim_id, Simulation.Status.DEPRECATED)
        click.echo(f"Simulation {sim_id} marked as deprecated.")
    elif update_type == "delete":
        result = api.delete_simulation(sim_id)
        click.echo(f"deleted simulation: {result['deleted']['simulation']}")
        if result["deleted"]["files"]:
            for file in result["deleted"]["files"]:
                click.echo(f"              file: {file}")


@remote.group(cls=RemoteSubGroup)
def token():
    """Manage user authentication tokens.
    """
    pass


@token.command("new")
@pass_api
@pass_config
def token_new(config: "Config", api: RemoteAPI):
    token = api.get_token()
    config.set_option(f'remote.{api.remote}.token', token)
    config.save()
    click.echo(f"Token added for remote {api.remote}.")


@token.command("delete")
@pass_api
@pass_config
def token_delete(config: "Config", api: RemoteAPI):
    try:
        config.delete_option(f'remote.{api.remote}.token')
        config.save()
        click.echo(f"Token for remote {api.remote} deleted.")
    except KeyError:
        click.echo(f"No token for remote {api.remote} found.")

