import click


@click.group()
def manifest():
    """Create/check manifest file."""
    pass


@manifest.command()
@click.argument("file_name", type=click.Path(exists=True))
def check(file_name):
    """Check manifest FILE_NAME."""
    from simdb.cli.manifest import InvalidManifest, Manifest

    manifest = Manifest()
    manifest.load(file_name)
    try:
        manifest.validate()
        click.echo("ok")
    except InvalidManifest as err:
        click.echo(err, err=True)


@manifest.command()
@click.argument("manifest_file", type=click.File("w"))
def create(manifest_file):
    """Create a new MANIFEST_FILE."""
    from pathlib import Path

    from simdb.cli.manifest import Manifest

    Manifest.from_template().save(manifest_file)
    path = Path(manifest_file.name).absolute()
    click.echo(f"Create manifest file {path}.")
