from enum import Enum, auto
from typing import Any, Tuple


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
    Parse the second half of a SimDB query argument and return the comparator type and value to be compared.

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
        raise ValueError(f"Malformed query string {value}.")
    try:
        return value, QueryType[comp[0].upper()]
    except KeyError:
        raise ValueError(f"Unknown query modifier {comp[0]}.")


def query_compare(query_type: QueryType, name: str, value: Any, compare: str) -> bool:
    """
    Perform a comparison between the compare string and the given value based on the comparison type given in
    query_type.

    :param query_type: The type of comparison being performed.
    :param name: The name of the field being compared. Used when reporting an error.
    :param value: The value being compared. This can be a string, a number or a numpy array.
    :param compare: The string representation of the value being compared against.
    :return: The result of the comparison.
    :raise ValueError: If the comparison could not be performed.
    """
    import numpy as np

    compare = compare.lower()
    if isinstance(value, str):
        value = value.lower()

    if query_type == QueryType.EQ:
        if isinstance(value, np.ndarray):
            return np.any(value == float(compare))
            # raise ValueError(f"Cannot compare value to array element {name}.")
        elif isinstance(value, int):
            return value == int(float(compare))
        elif isinstance(value, float):
            return value == float(compare)
        else:
            return str(value) == compare
    elif query_type == QueryType.NE:
        if isinstance(value, np.ndarray):
            return np.any(value != float(compare))
            # raise ValueError(f"Cannot compare value to array element {name}.")
        elif isinstance(value, int):
            return value != int(float(compare))
        elif isinstance(value, float):
            return value != float(compare)
        else:
            return str(value) != compare
    elif query_type == QueryType.IN:
        if isinstance(value, np.ndarray):
            return float(compare) in value
        elif isinstance(value, int) or isinstance(value, float):
            raise ValueError(
                f"Cannot use 'in' query selection for scalar metadata field {name}."
            )
        elif value is not None:
            return compare in str(value)
    elif query_type == QueryType.NI:
        if isinstance(value, np.ndarray):
            return float(compare) in value
        elif isinstance(value, int) or isinstance(value, float):
            raise ValueError(
                f"Cannot use 'ni' query selection for scalar metadata field {name}."
            )
        elif value is not None:
            return compare not in str(value)
    elif query_type == QueryType.GT:
        if isinstance(value, np.ndarray):
            return np.all(value > float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value > float(compare)
        elif value is not None:
            return value > compare
    elif query_type == QueryType.GE:
        if isinstance(value, np.ndarray):
            return np.all(value >= float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value >= float(compare)
        elif value is not None:
            return value >= compare
    elif query_type == QueryType.LT:
        if isinstance(value, np.ndarray):
            return np.all(value < float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value < float(compare)
        elif value is not None:
            return value < compare
    elif query_type == QueryType.LE:
        if isinstance(value, np.ndarray):
            return np.all(value <= float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value <= float(compare)
        elif value is not None:
            return value <= compare
    elif query_type == QueryType.AGT:
        if isinstance(value, np.ndarray):
            return np.any(value > float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value > float(compare)
        else:
            raise ValueError(
                f"Cannot use 'agt' query selection for non-array metadata field {name}."
            )
    elif query_type == QueryType.AGE:
        if isinstance(value, np.ndarray):
            return np.any(value >= float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value >= float(compare)
        else:
            raise ValueError(
                f"Cannot use 'age' query selection for non-array metadata field {name}."
            )
    elif query_type == QueryType.ALT:
        if isinstance(value, np.ndarray):
            return np.any(value < float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value < float(compare)
        else:
            raise ValueError(
                f"Cannot use 'alt' query selection for non-array metadata field {name}."
            )
    elif query_type == QueryType.ALE:
        if isinstance(value, np.ndarray):
            return np.any(value <= float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value <= float(compare)
        else:
            raise ValueError(
                f"Cannot use 'ale' query selection for non-array metadata field {name}."
            )
    else:
        raise ValueError(f"Unknown query type {query_type}.")

    return False
