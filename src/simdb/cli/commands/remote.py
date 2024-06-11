import re
import sys
import uuid
import shutil

import click
from collections.abc import Iterable
from typing import List, TYPE_CHECKING, Optional, Tuple, Union, Type
from semantic_version import Version
from pprint import pprint

from ..remote_api import RemoteAPI
from . import pass_config, check_meta_args
from .utils import print_simulations, print_trace
from ...notifications import Notification
from .validators import validate_non_negative, validate_positive
from ...database.models.simulation import Simulation

pass_api = click.make_pass_decorator(RemoteAPI)

if TYPE_CHECKING or "sphinx" in sys.modules:
    from ...config import Config
    from click import Context


class RemoteGroup(click.Group):
    def parse_args(self, ctx, args):
        cmds = []
        skip_next = False
        for a in args:
            if a.startswith("--") or a.startswith("-"):
                skip_next = True
                continue
            if skip_next:
                skip_next = False
                continue
            cmds.append(a)
        if "--help" in args:
            if cmds and cmds[0] in self.commands:
                cmd = self.commands[cmds[0]]
                if isinstance(cmd, click.Group):
                    grp = cmd
                    for c in cmds[1:]:
                        if c in grp.commands:
                            cmd = grp.commands[c]
                        else:
                            raise click.ClickException(f"Unknown subcommand {c}")
                ctx.command = cmd
            args = ["--help"]
        elif cmds and cmds[0] in self.commands:
            args.insert(args.index(cmds[0]), "")
        super().parse_args(ctx, args)


class RemoteSubGroup(click.Group):
    def format_usage(self, ctx, formatter):
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(
            ctx.command_path.replace("remote", f"remote [NAME] {self.name}"),
            " ".join(pieces),
        )


class _RemoteCommand(click.Command):
    subgroup: str = ""

    def format_usage(self, ctx, formatter):
        pieces = self.collect_usage_pieces(ctx)
        if self.subgroup:
            formatter.write_usage(
                ctx.command_path.replace(
                    "remote", f"remote [NAME] {self.subgroup} {self.name}"
                ),
                " ".join(pieces),
            )
        else:
            formatter.write_usage(
                ctx.command_path.replace("remote", f"remote [NAME] {self.name}"),
                " ".join(pieces),
            )


def remote_command_cls(subgroup: str = "") -> Type:
    """
    Customise the RemoteCommand class to hold the name of the subgroup if provided. This is required to properly format
    the help string for subgroup commands.
    """
    sub_command_cls = type("SubCommandCls", (_RemoteCommand,), {"subgroup": subgroup})
    return sub_command_cls


def is_empty(value) -> bool:
    return any(value) if isinstance(value, Iterable) else bool(value)


@click.group(cls=RemoteGroup, invoke_without_command=True)
@click.pass_context
@pass_config
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
@click.argument("name", required=False)
def remote(
    config: "Config",
    ctx: "Context",
    username: Optional[str],
    password: Optional[str],
    name: str,
):
    """Interact with the remote SimDB service.

    If NAME is provided this determines which remote server to communicate with, otherwise the server in the config file
    with default=True is used.
    """
    if not ctx.invoked_subcommand and not any(is_empty(i) for i in ctx.params.values()):
        click.echo(ctx.get_help())
    else:
        if ctx.invoked_subcommand in ["config"]:
            pass
        elif ctx.invoked_subcommand:
            if ctx.invoked_subcommand == "token" and sys.argv[-1] == "new":
                ctx.obj = RemoteAPI(name, username, password, config, use_token=False)
            else:
                ctx.obj = RemoteAPI(name, username, password, config)
        else:
            click.echo(ctx.get_help())


@remote.command("test", cls=remote_command_cls())
@pass_api
def remote_test(api: RemoteAPI):
    """
    Test that the remote is valid.
    """
    remote_version = api.get_api_version()
    print(f"Remote is valid (remote API version: {remote_version})")


@remote.command("directory", cls=remote_command_cls())
@pass_api
def remote_directory(api: RemoteAPI):
    """
    Print the storage directory of the remote.
    """
    if api.version < Version("1.2.0"):
        raise click.ClickException(
            "Command not available with this remote. Requires API version >= 1.2."
        )
    print(api.get_directory())


@remote.group("config", cls=RemoteSubGroup)
def remote_config():
    """
    Configure the available remotes.
    """
    pass


@remote_config.command("default", cls=remote_command_cls("config"))
@pass_config
def config_default(config: "Config"):
    """
    Print the default remote.
    """
    click.echo(config.default_remote)


@remote_config.command("list", cls=remote_command_cls("config"))
@pass_config
def config_list(config: "Config"):
    """
    List available remotes.
    """
    r = re.compile(r"remote\.(.*)\.url: (.*)")
    for option in config.list_options():
        m = r.match(option)
        if m:
            options = {
                "firewall": config.get_option(f"remote.{m[1]}.firewall", default=None),
                "username": config.get_option(f"remote.{m[1]}.username", default=None),
            }
            options_str = ", ".join(
                f"{k}: {v}" for k, v in options.items() if v is not None
            )
            click.echo(
                f"{m[1]}: {m[2]}"
                + (f" [{options_str}]" if options_str else "")
                + (" (default)" if m[1] == config.default_remote else "")
            )


@remote_config.command("new", cls=remote_command_cls("config"))
@pass_config
@click.argument("name", required=True)
@click.argument("url", required=True)
@click.option(
    "--firewall",
    help="Specify the remote is behind a login firewall and what type it is.",
    type=click.Choice(["F5"], case_sensitive=False),
)
@click.option("--username", help="Username to use for remote.", type=str)
@click.option(
    "--default",
    is_flag=True,
    help="Set the new remote as the default.",
)
def config_new(
    config: "Config",
    name: str,
    url: str,
    firewall: Optional[str],
    username: Optional[str],
    default: bool,
):
    """
    Add a new remote.
    """
    config.set_option(f"remote.{name}.url", url)
    if firewall is not None:
        config.set_option(f"remote.{name}.firewall", firewall)
    if username is not None:
        config.set_option(f"remote.{name}.username", username)
    if default:
        config.default_remote = name
    config.save()


@remote_config.command("delete", cls=remote_command_cls("config"))
@pass_config
@click.argument("name", required=True)
def config_delete(config: "Config", name: str):
    """
    Delete a remote.
    """
    config.delete_section(f"remote.{name}")
    config.save()


@remote_config.command("set-default", cls=remote_command_cls("config"))
@pass_config
@click.argument("name", required=True)
def config_set_default(config: "Config", name: str):
    """
    Set a remote as default.
    """
    config.default_remote = name
    config.save()


@remote_config.command("get-default", cls=remote_command_cls("config"))
@pass_config
def config_get_default(config: "Config"):
    """
    Get the name of the default remote.
    """
    click.echo(config.default_remote)


@remote_config.command("set-option", cls=remote_command_cls("config"))
@pass_config
@click.argument("name", required=True)
@click.argument("option", required=True)
@click.argument("value", required=True)
def config_set_option(config: "Config", name: str, option: str, value: str):
    """
    Set a configuration option for a given remote.
    """
    config.set_option(f"remote.{name}.{option}", value)
    config.save()


@remote.group(cls=RemoteSubGroup)
def watcher():
    """Manage simulation watchers on REMOTE SimDB server."""
    pass


@watcher.command("list", cls=remote_command_cls("watcher"))
@pass_api
@click.argument("sim_id")
def list_watchers(api: RemoteAPI, sim_id: str):
    """List watchers for simulation with given SIM_ID (UUID or alias)."""
    watchers = api.list_watchers(sim_id)
    if watchers:
        click.echo(f"Watchers for simulation {sim_id}:")
        for watcher in watchers:
            click.echo(watcher)
    else:
        click.echo(f"no watchers found for simulation {sim_id}")


@watcher.command("remove", cls=remote_command_cls("watcher"))
@pass_api
@pass_config
@click.argument("sim_id")
@click.option("-u", "--user", help="Name of the user to remove as a watcher.")
def remove_watcher(config: "Config", api: RemoteAPI, sim_id: str, user: str):
    """Remove a user from list of watchers on a simulation with given SIM_ID (UUID or alias)."""
    if not user:
        user = config.get_string_option("user.name")
    if not user:
        raise click.ClickException(
            "User not provided and user.name not found in config."
        )
    api.remove_watcher(sim_id, user)
    click.echo(f"Watcher successfully removed for simulation {sim_id}")


@watcher.command("add", cls=remote_command_cls("watcher"))
@pass_api
@pass_config
@click.argument("sim_id")
@click.option("-u", "--user", help="Name of the user to add as a watcher.")
@click.option("-e", "--email", help="Email of the user to add as a watcher.")
@click.option(
    "-n",
    "--notification",
    type=click.Choice(list(i.name for i in Notification), case_sensitive=False),
    default=Notification.ALL.name,
    show_default=True,
)
def add_watcher(
    config: "Config",
    api: RemoteAPI,
    sim_id: str,
    user: Optional[str],
    email: Optional[str],
    notification: str,
):
    """Register a user as a watcher for a simulation with given SIM_ID (UUID or alias)."""
    if not user:
        user = config.get_string_option("user.name", default=None)
    if not user:
        raise click.ClickException(
            "User not provided and user.name not found in config."
        )
    if not email:
        email = config.get_string_option("user.email", default=None)
    if not email:
        raise click.ClickException(
            "Email not provided and user.email not found in config."
        )
    api.add_watcher(sim_id, user, email, getattr(Notification, notification))
    click.echo(f"Watcher successfully added for simulation {sim_id}")


@remote.command("schema", cls=remote_command_cls())
@pass_api
@click.option(
    "-d",
    "--depth",
    help="Limit the depth of elements of the schema printed to the console.",
    default=2,
    show_default=True,
    callback=validate_positive,
)
def remote_show_validation_schema(api: RemoteAPI, depth: int):
    """Show validation schemas for the given remote."""
    schemas = api.get_validation_schemas()
    for schema in schemas:
        pprint(schema, indent=2, depth=depth, width=shutil.get_terminal_size().columns)


@remote.command("list", cls=remote_command_cls())
@pass_api
@pass_config
@click.option(
    "-m",
    "--meta-data",
    "meta",
    help="Additional meta-data field to print.",
    multiple=True,
    default=[],
    metavar="NAME",
)
@click.option(
    "-l",
    "--limit",
    help="Limit number of returned entries (use 0 for no limit).",
    default=100,
    show_default=True,
    callback=validate_non_negative,
)
def remote_list(config: "Config", api: RemoteAPI, meta: List[str], limit: int):
    """List simulations available on remote."""
    check_meta_args(meta)
    simulations = api.list_simulations(meta, limit)
    print_simulations(simulations, verbose=config.verbose, metadata_names=meta)


@remote.command("version", cls=remote_command_cls())
@pass_api
def remote_version(api: RemoteAPI):
    """Show the SimDB version of the remote."""
    click.echo(f"Remote '{api.remote}' SimDB version: {api.server_version}")


@remote.command("info", cls=remote_command_cls())
@pass_api
@click.argument("sim_id")
def remote_info(api: RemoteAPI, sim_id: str):
    """Print information about simulation with given SIM_ID (UUID or alias) from remote."""
    simulation = api.get_simulation(sim_id)
    click.echo(str(simulation))


@remote.command("trace", cls=remote_command_cls())
@pass_api
@click.argument("sim_id")
def remote_trace(api: RemoteAPI, sim_id: str):
    """Print provenance trace of simulation with given SIM_ID (UUID or alias) from remote.

    This shows a history of simulations that this simulation has replaced or been replaced by and
    what those simulations replaced or where replaced by and so on.

    If the outputs of this simulation are used as inputs of other simulations or if the inputs
    are generated by other simulations then these dependencies are also reported.
    """
    trace_data = api.trace_simulation(sim_id)
    print_trace(trace_data)


@remote.command("query", cls=remote_command_cls())
@pass_api
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
    "-l",
    "--limit",
    help="Limit number of returned entries (use 0 for no limit).",
    default=100,
    show_default=True,
    callback=validate_non_negative,
)
def remote_query(
    config: "Config",
    api: RemoteAPI,
    constraints: List[str],
    meta: Tuple[str],
    limit: int,
):
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
    if not constraints:
        raise click.ClickException("At least one constraint must be provided.")

    check_meta_args(meta)
    for constraint in constraints:
        if "=" not in constraint:
            raise click.ClickException(f"Invalid constraint {constraint}.")

    simulations = api.query_simulations(constraints, meta, limit)

    names: List[str] = []
    for constraint in constraints:
        name, _ = constraint.split("=")
        names.append(name)
    names += meta

    print_simulations(simulations, verbose=config.verbose, metadata_names=names)


@remote.command("update", cls=remote_command_cls())
@pass_api
@click.argument("sim_id")
@click.argument(
    "update_type",
    type=click.Choice(["validate", "accept", "deprecate"], case_sensitive=False),
)
def remote_update(api: RemoteAPI, sim_id: str, update_type: str):
    """Mark remote simulation as published."""
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
    """Manage user authentication tokens."""
    pass


@token.command("new", cls=remote_command_cls("token"))
@pass_api
@pass_config
def token_new(config: "Config", api: RemoteAPI):
    """
    Create a new token for the given remote.
    """
    token = api.get_token()
    config.set_option(f"remote.{api.remote}.token", token)
    config.save()
    click.echo(f"Token added for remote {api.remote}.")


@token.command("delete", cls=remote_command_cls("token"))
@pass_api
@pass_config
def token_delete(config: "Config", api: RemoteAPI):
    """
    Delete the existing token for the given remote.
    """
    try:
        config.delete_option(f"remote.{api.remote}.token")
        config.save()
        click.echo(f"Token for remote {api.remote} deleted.")
    except KeyError:
        click.echo(f"No token for remote {api.remote} found.")


@remote.group(cls=RemoteSubGroup)
def admin():
    """Run admin commands on REMOTE SimDB server (requires admin privileges).

    Requires user to have admin privileges on remote.
    """
    pass


@admin.command("set-meta", cls=remote_command_cls("admin"))
@pass_api
@click.argument("sim_id")
@click.argument("key")
@click.argument("value")
@click.option(
    "-t",
    "--type",
    type=click.Choice(["string", "UUID", "int", "float"], case_sensitive=False),
    default="string",
)
def admin_set_meta(api: RemoteAPI, sim_id: str, key: str, value: str, type: str):
    """Add or update a metadata value for the given simulation."""
    new_value: Union[str, uuid.UUID, int, float] = value
    if type == "UUID":
        new_value = uuid.UUID(value)
    elif type == "int":
        new_value = int(value)
    elif type == "float":
        new_value = float(value)
    old_value = api.set_metadata(sim_id, key, new_value)
    if old_value:
        click.echo(f"Update {key} for simulation {sim_id}: {old_value} -> {new_value}")
    else:
        click.echo(f"Added {key} for simulation {sim_id} with value '{new_value}'")


@admin.command("set-status", cls=remote_command_cls("admin"))
@pass_api
@click.argument("sim_id")
@click.argument(
    "value",
    type=click.Choice(
        [str(i).replace("Status.", "") for i in Simulation.Status], case_sensitive=False
    ),
)
def admin_set_status(api: RemoteAPI, sim_id: str, value: str):
    """Update the status metadata value for the given simulation."""
    #old_value = api.set_metadata(sim_id, "status", value)
    old_value = api.update_simulation(sim_id, Simulation.Status(value.lower()))
    if old_value:
        click.echo(f"Update status for simulation {sim_id}: {old_value} -> {value}")
    else:
        click.echo(f"Added status for simulation {sim_id} with value '{value}'")


@admin.command("del-meta", cls=remote_command_cls("admin"))
@pass_api
@click.argument("sim_id")
@click.argument("key")
def admin_del_meta(api: RemoteAPI, sim_id: str, key: str):
    """Remove a metadata value for the given simulation."""
    api.delete_metadata(sim_id, key)
    click.echo(f"Deleted {key} for simulation {sim_id}")


@admin.command("delete", cls=remote_command_cls("admin"))
@pass_api
@click.argument("sim_id")
def admin_del_sim(api: RemoteAPI, sim_id: str):
    """Delete a simulation."""
    api.delete_simulation(sim_id)
    click.echo(f"Deleted simulation {sim_id}")
