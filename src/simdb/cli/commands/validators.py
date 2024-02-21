import click


def validate_non_negative(ctx, param, value):
    if value < 0:
        raise click.BadParameter("must be non-negative")
    return value


def validate_positive(ctx, param, value):
    if value <= 0:
        raise click.BadParameter("must be positive")
    return value
