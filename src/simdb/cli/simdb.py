import copy
import sys
from typing import TextIO

import click

from simdb import __version__
from simdb.config import Config

from .commands.alias import alias
from .commands.config import config
from .commands.database import database
from .commands.manifest import manifest
from .commands.provenance import provenance
from .commands.remote import remote
from .commands.simulation import simulation

g_debug = False


def recursive_help(cmd, parent=None):
    ctx = click.core.Context(cmd, info_name=cmd.name, parent=parent)
    click.echo(cmd.get_help(ctx))
    click.echo()
    commands = getattr(cmd, "commands", {})
    for sub in commands.values():
        recursive_help(sub, ctx)


class AliasCommandGroup(click.Group):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)

    def add_command(self, cmd, name=None, aliases=None):
        super().add_command(cmd, name)
        aliases = aliases if aliases is not None else []
        for a in aliases:
            cmd = copy.copy(cmd)
            cmd.short_help = f"Alias for {name}."
            self.commands[a] = cmd

    def get_command(self, ctx, cmd_name):
        return self.commands.get(cmd_name)

    def list_commands(self, ctx):
        return sorted(self.commands)


# @tui()
@click.group("simdb", cls=AliasCommandGroup)
@click.version_option(__version__)
@click.option("-d", "--debug", is_flag=True, help="Run in debug mode.")
@click.option("-v", "--verbose", is_flag=True, help="Run with verbose output.")
@click.option("-c", "--config-file", type=click.File("r"), help="Config file to load.")
@click.pass_context
def cli(ctx, debug: bool, verbose: bool, config_file: TextIO):
    if not ctx.obj:
        ctx.obj = Config()
        ctx.obj.load(config_file)
        ctx.obj.debug = debug
        ctx.obj.verbose = verbose
    global g_debug
    g_debug = debug


@cli.command(hidden=True)
def dump_help():
    recursive_help(cli)


def add_commands():
    cli.add_command(manifest)
    cli.add_command(alias)
    cli.add_command(simulation, aliases=["sim"], name="simulation")
    cli.add_command(config)
    cli.add_command(database)
    cli.add_command(remote)
    cli.add_command(provenance)


add_commands()


def main() -> None:
    """
    Main CLI entry function

    :return: None
    """
    try:
        cli()
    except Exception as ex:
        click.echo(f"Error: {ex}", err=True)
        if g_debug:
            raise ex
        sys.exit(1)
