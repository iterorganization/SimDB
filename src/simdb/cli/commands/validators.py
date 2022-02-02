import click


def validate_limit(ctx, param, value):
    if value < 0:
        raise click.BadParameter("must be non-negative")
    return value
