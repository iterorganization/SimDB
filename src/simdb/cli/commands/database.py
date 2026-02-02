import click

from simdb.database import get_local_db

from . import pass_config


@click.group()
def database():
    """Manage local simulation database."""
    pass


@database.command()
@pass_config
def clear(config):
    """Clear the database."""

    db = get_local_db(config)
    db.reset()
