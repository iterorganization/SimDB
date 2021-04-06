import click

from . import pass_config


class AliasCommand(click.Command):
    def parse_args(self, ctx, args):
        if len(args) < sum(1 for i in self.params if isinstance(i, click.Argument)):
            args.insert(0, '')
        super().parse_args(ctx, args)


@click.group()
def alias():
    """Query remote and local aliases.
    """
    pass


@alias.command(cls=AliasCommand)
@pass_config
@click.argument("remote", required=False)
@click.argument("value")
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
def search(config, remote, value, username, password):
    """Search the REMOTE for all aliases that contain the given VALUE.
    """
    from ..remote_api import RemoteAPI
    from ...database import get_local_db

    api = RemoteAPI(remote, username, password, config)
    simulations = api.list_simulations()

    db = get_local_db(config)
    simulations += db.list_simulations()

    aliases = [sim.alias for sim in simulations if value in sim.alias]
    for alias in aliases:
        click.echo(alias)


@alias.command(cls=AliasCommand)
@pass_config
@click.argument("remote", required=False)
@click.option("--username", help="Username used to authenticate with the remote.")
@click.option("--password", help="Password used to authenticate with the remote.")
def list(config, remote, username, password):
    """List aliases from the local database and the REMOTE (if specified)."""
    from ..remote_api import RemoteAPI
    from ...database import get_local_db

    if remote:
        remote_simulations = []
        api = RemoteAPI(remote, username, password, config)
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
