from enum import Enum, auto
from typing import Any
import numpy as np


class QueryType(Enum):
    EQ = auto()
    IN = auto()


def parse_query_arg(value: str) -> (str, str):
    if value.startswith('in:'):
        return value.replace('in:', ''), QueryType.IN
    else:
        return value, QueryType.EQ


def query_compare(query_type: QueryType, name: str, value: Any, compare: str):
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
    else:
        raise ValueError(f"Unknown query type {query_type}")
