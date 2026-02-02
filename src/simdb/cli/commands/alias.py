import sys
from typing import TYPE_CHECKING, Iterable

import click

from simdb.cli.remote_api import RemoteAPI
from simdb.database import get_local_db

from . import pass_config

pass_api = click.make_pass_decorator(RemoteAPI)

if TYPE_CHECKING or "sphinx" in sys.modules:
    from click import Context

    from simdb.config import Config


class AliasCommand(click.Command):
    def parse_args(self, ctx, args):
        if len(args) < sum(1 for i in self.params if isinstance(i, click.Argument)):
            args.insert(0, "")
        super().parse_args(ctx, args)


class AliasGroup(click.Group):
    def parse_args(self, ctx, args):
        if args and args[0] in self.commands:
            args.insert(0, "")
        super().parse_args(ctx, args)


class AliasSubGroup(click.Group):
    def format_usage(self, ctx, formatter):
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(
            ctx.command_path.replace("remote", "remote [NAME]"), " ".join(pieces)
        )


def is_empty(value) -> bool:
    return any(value) if isinstance(value, Iterable) else bool(value)


@click.group(cls=AliasGroup, invoke_without_command=True)
@click.pass_context
@pass_config
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
@click.argument("remote", required=False)
def alias(config: "Config", ctx: "Context", remote, username, password):
    """Query remote and local aliases."""
    if not ctx.invoked_subcommand and not any(is_empty(i) for i in ctx.params.values()):
        click.echo(ctx.get_help())
    elif "--help" not in sys.argv and ctx.invoked_subcommand:
        ctx.obj = RemoteAPI(remote, username, password, config)


@alias.command("make-unique", cls=AliasCommand)
@pass_api
@pass_config
@click.argument("alias")
def alias_make_unique(config: "Config", api: RemoteAPI, alias: str):
    """Make the given alias unique, checking locally stored simulations and the remote."""

    trans = str.maketrans("#/()=,*%", "________")
    alias = alias.translate(trans)

    simulations = api.list_simulations()

    db = get_local_db(config)
    simulations += db.list_simulations()

    aliases = [sim.alias for sim in simulations]
    n = 1
    base = alias
    while alias in aliases:
        alias = f"{base}-{n}"
        n += 1

    click.echo(alias)


@alias.command("search", cls=AliasCommand)
@pass_api
@pass_config
@click.argument("alias")
def alias_search(config: "Config", api: RemoteAPI, alias: str):
    """Search the REMOTE for all aliases that contain the given VALUE."""
    simulations = api.list_simulations()

    db = get_local_db(config)
    simulations += db.list_simulations()

    aliases = [sim.alias for sim in simulations if alias in sim.alias]
    for alias in aliases:
        click.echo(alias)


@alias.command("list", cls=AliasCommand)
@pass_api
@pass_config
@click.option("--local", help="Only list the local aliases.", is_flag=True)
def alias_list(config: "Config", api: RemoteAPI, local: bool):
    """List aliases from the local database and the REMOTE (if specified)."""

    if not local:
        remote_simulations = []
        if api.has_url():
            remote_simulations = api.list_simulations()
        else:
            click.echo(
                "The Remote Server has not been specified in the configuration file. Please set remote-url"
            )

        click.echo("Remote:")
        for sim in remote_simulations:
            click.echo(f"  {sim.alias}")

    db = get_local_db(config)
    local_simulations = db.list_simulations()

    click.echo("Local:")
    for sim in local_simulations:
        click.echo(f"  {sim.alias}")
