from typing import Iterable

import click

from simdb.config import Config

pass_config = click.make_pass_decorator(Config)


def check_meta_args(args: Iterable[str]):
    for arg in args:
        if "=" in arg:
            click.ClickException(
                f"Invalid additional meta-data field {arg}, must not contain ="
            )


def query_help(scope: str, command: str) -> str:
    """Help text shared by the local and remote query commands."""
    return f"""Perform a metadata query to find matching {scope} simulations.

    \b
    Each constraint must be in the form:
        NAME=[mod]VALUE

    \b
    Where `[mod]` is an optional query modifier. Available query modifiers are:
        eq:  - This checks for equality (this is the same behaviour as not providing
               any modifier).
        ne:  - This checks for values that do not equal.
        in:  - This searches inside the value instead of looking for exact matches.
        ni:  - This searches inside the value for elements that do not match.
        gt:  - This checks for values greater than the given quantity.
        agt: - This checks for any array elements are greater than the given quantity.
        ge:  - This checks for values greater than or equal to the given quantity.
        age: - This checks for any array elements are greater than or equal to the given
               quantity.
        lt:  - This checks for values less than the given quantity.
        alt: - This checks for any array elements are less than the given quantity.
        le:  - This checks for values less than or equal to the given quantity.
        ale: - This checks for any array elements are less than or equal to the given
               quantity.

    \b
    For the following modifiers, VALUE should not be provided.
        exist: - This returns simulations where metadata with NAME exists, regardless
                 of the value.

    \b
    Modifier examples:
        alias=eq:foo                     performs exact match
        code.name=in:foo                 matches all names containing foo
        global_quantities.r0.value=gt:6  matches all simulations where r0 is > 6
        time=agt:5                       matches all simulations where any time
                                         value is > 5
        sequence=exist:                  matches all simulations that have
                                         "sequence" metadata values

    \b
    Any string comparisons are done in a case-insensitive manner. If multiple
    constraints are provided then simulations are returned that match all given
    constraints.

    \b
    Examples:
        simdb {command} query workflow.name=in:test
            finds all simulations where workflow.name contains test
            (case-insensitive)
        simdb {command} query global_quantities.r0.value=gt:6 machine=ITER
            finds all ITER simulations where r0 is > 6
    """
