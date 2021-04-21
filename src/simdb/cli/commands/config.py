import click
import re

from . import pass_config


@click.group()
def config():
    """Query/update application configuration.
    """
    pass


@config.command()
@pass_config
@click.argument("option")
def get(config, option):
    """Get the OPTION.
    """
    click.echo(config.get_option(option))


@config.command()
@pass_config
@click.argument("option")
@click.argument("value")
def set(config, option, value):
    """Set the OPTION to the given VALUE.
    """
    config.set_option(option, value)
    config.save()


@config.command()
@pass_config
@click.argument("option")
def delete(config, option):
    """Delete the OPTION.
    """
    config.delete_option(option)
    config.save()
    click.echo("Success.")


@config.command()
@pass_config
def list(config):
    """List all configurations OPTIONS set.
    """
    r = re.compile(r'(remote\..*\.token: )(.*)')
    for i in config.list_options():
        m = r.match(i)
        if m:
            i = f'{m[1]}********'
        click.echo(i)


@config.command()
@pass_config
def path(config):
    """Print the location of the user configuration file.
    """
    click.echo(config.user_config_path)
