from enum import Enum, auto
from typing import Any


class QueryType(Enum):
    NONE = auto()
    EQ = auto()
    IN = auto()
    GT = auto()
    GE = auto()
    LT = auto()
    LE = auto()


def parse_query_arg(value: str) -> (str, str):
    *comp, value = value.split(':')
    if not comp:
        return value, QueryType.NONE
    if len(comp) > 1:
        raise ValueError(f'Malformed query string {value}.')
    try:
        return value, QueryType[comp[0].upper()]
    except KeyError:
        raise ValueError(f'Unknown query modifier {comp[0]}.')


def query_compare(query_type: QueryType, name: str, value: Any, compare: str):
    import numpy as np
    if query_type == QueryType.EQ:
        if isinstance(value, np.ndarray):
            raise ValueError(f"Cannot compare value to array element {name}.")
        else:
            return str(value) == compare
    elif query_type == QueryType.IN:
        if isinstance(value, np.ndarray):
            return float(compare) in value
        elif isinstance(value, int):
            raise ValueError(f"Cannot use 'in' query selection for integer metadata field {name}.")
        else:
            return compare in str(value)
    elif query_type == QueryType.GT:
        if isinstance(value, np.ndarray):
            return np.any(value > float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value > float(compare)
        else:
            return value > compare
    elif query_type == QueryType.GE:
        if isinstance(value, np.ndarray):
            return np.any(value >= float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value >= float(compare)
        else:
            return value >= compare
    elif query_type == QueryType.LT:
        if isinstance(value, np.ndarray):
            return np.any(value < float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value < float(compare)
        else:
            return value < compare
    elif query_type == QueryType.LE:
        if isinstance(value, np.ndarray):
            return np.any(value <= float(compare))
        elif isinstance(value, int) or isinstance(value, float):
            return value <= float(compare)
        else:
            return value <= compare
    else:
        raise ValueError(f"Unknown query type {query_type}.")
