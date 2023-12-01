import click
from typing import Iterable

from ...config import Config

pass_config = click.make_pass_decorator(Config)


def check_meta_args(args: Iterable[str]):
    for arg in args:
        if "=" in arg:
            click.ClickException(
                f"Invalid additional meta-data field {arg}, must not contain ="
            )
