import click

from .commands.manifest import manifest
from .commands.alias import alias
from .commands.simulation import simulation
from .commands.config import config
from .commands.database import database
from .commands.remote import remote
from ..config import Config
from .. import __version__


g_debug = False


@click.group("simdb")
@click.version_option(__version__)
@click.option("-d", "--debug", is_flag=True, help="Run in debug mode.")
@click.option("-v", "--verbose", is_flag=True, help="Run with verbose output.")
@click.pass_context
def cli(ctx, debug, verbose):
    ctx.obj = Config()
    ctx.obj.load()
    ctx.obj.set_debug(debug)
    ctx.obj.set_verbose(verbose)
    global g_debug
    g_debug = debug


cli.add_command(manifest)
cli.add_command(alias)
cli.add_command(simulation)
cli.add_command(config)
cli.add_command(database)
cli.add_command(remote)


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
