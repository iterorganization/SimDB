import click

from . import pass_config


@click.group()
def alias():
    """Query remote and local aliases.
    """
    pass


@alias.command()
@pass_config
@click.argument("remote")
@click.argument("value")
def search(config, remote, value):
    """Search the REMOTE for all aliases that contain the given VALUE.
    """
    from ..remote_api import RemoteAPI
    from ...database import get_local_db

    api = RemoteAPI(remote, config)
    simulations = api.list_simulations()

    db = get_local_db(config)
    simulations += db.list_simulations()

    aliases = [sim.alias for sim in simulations if sim.alias.contains(value)]
    for alias in aliases:
        click.echo(alias)


@alias.command()
@pass_config
@click.argument("remote", required=False)
def list(config, remote):
    """List aliases from the local database and the REMOTE (if specified)."""
    from ..remote_api import RemoteAPI
    from ...database import get_local_db

    if remote:
        remote_simulations = []
        api = RemoteAPI(remote, config)
        if api.has_url():
            remote_simulations = api.list_simulations()
        else:
            click.echo('The Remote Server has not been specified in the configuration file. Please set remote-url')

        click.echo("Remote:")
        for sim in remote_simulations:
            click.echo(f"  {sim.alias}")

    db = get_local_db(config)
    local_simulations = db.list_simulations()

    click.echo("Local:")
    for sim in local_simulations:
        click.echo(f"  {sim.alias}")
