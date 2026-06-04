from enum import Enum, auto
from typing import Tuple


class QueryType(Enum):
    """
    SimDB query comparator options.
    """

    NONE = auto()
    EQ = auto()  # Equal
    NE = auto()  # Not Equal
    IN = auto()  # Containing
    NI = auto()  # Not containing
    GT = auto()  # Greater than
    GE = auto()  # Greater than or equal
    LT = auto()  # Less than
    LE = auto()  # Less than or equal
    AGT = auto()  # Any greater than
    AGE = auto()  # Any greater than or equal
    ALT = auto()  # Any less than
    ALE = auto()  # Any less than or equal
    EXIST = auto()


def parse_query_arg(value: str) -> Tuple[str, QueryType]:
    """
    Parse the second half of a SimDB query argument and return the comparator type and
    value to be compared.

    The strings being parsed will be of the form:
        value
        comparator:value

    If no comparator is given then QueryType.EQ is returned as a default.

    :param value: The query string to parse.
    :return: The extracted value and comparator.
    """
    if not value:
        return value, QueryType.NONE
    *comp, value = value.split(":")
    if not comp:
        return value, QueryType.EQ
    if len(comp) > 1:
        raise ValueError(f"Malformed query string {value}.") from None
    try:
        return value, QueryType[comp[0].upper()]
    except KeyError:
        raise ValueError(f"Unknown query modifier {comp[0]}.") from None
