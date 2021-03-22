from collections import deque
from typing import Dict, Any, Union, List, Tuple, Deque, Type

FLATTEN_DICT_DELIM = '.'


def flatten_dict(out_dict: Dict[str, Any], in_dict: Dict[str, Union[Dict, List, Any]], prefix: Tuple=()):
    for key, value in in_dict.items():
        if isinstance(value, dict):
            flatten_dict(out_dict, value, prefix + (key,))
        elif isinstance(value, list):
            for i, el in enumerate(value):
                flatten_dict(out_dict, el, prefix + (f'{key}#{i + 1}',))
        else:
            out_dict[FLATTEN_DICT_DELIM.join(prefix + (key,))] = value


def _parse_index(head: str) -> Tuple[bool, str, int]:
    tokens = head.split('#')
    if len(tokens) > 1 and tokens[-1].isdigit():
        return True, '#'.join(tokens[:-1]), int(tokens[-1])
    return False, head, 0


def _unflatten_value(out_dict: Dict[str, Union[Dict, Any]], key: Deque[str], value: Any) -> None:
    head = key.popleft()
    tail = key
    is_index, head, index = _parse_index(head)
    if tail:
        if head not in out_dict:
            out_dict[head] = [] if is_index else {}
        el = out_dict[head]
        if is_index:
            while index > len(el):
                el.append({})
            el = el[index-1]
        _unflatten_value(el, tail, value)
    else:
        out_dict[head] = value


def unflatten_dict(in_dict: Dict[str, Any]) -> Dict[str, Union[Dict, Any]]:
    out_dict: Dict[str, Union[Dict, List, Any]] = {}
    for key, value in in_dict.items():
        _unflatten_value(out_dict, deque(key.split(FLATTEN_DICT_DELIM)), value)
    return out_dict


def checked_get(data: Dict[str, Any], key, type: Type):
    if not isinstance(data[key], type):
        raise ValueError("corrupted %s - expected %s" % (key, str(type)))
    return data[key]
