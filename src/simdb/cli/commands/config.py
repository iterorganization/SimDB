import click

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
    for i in config.list_options():
        click.echo(i)
