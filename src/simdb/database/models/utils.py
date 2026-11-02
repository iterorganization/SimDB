from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple, Type, Union, cast

FLATTEN_DICT_DELIM = "."


def flatten_dict(
    data: Dict[str, Any],
    prefix: str = "",
    delim: str = ".",
) -> Dict[str, Any]:
    """
    Recursively flattens a nested dictionary, representing nested structures with keys
    delimited by a string, and lists with index suffixes.

    Example:
        >>> flatten_dict({"a": {"b": 1}, "c": [2, {"d": 3}]})
        {'a.b': 1, 'c#1': 2, 'c#2.d': 3}

    :param data: The nested dictionary to flatten.
    :param prefix: The prefix to prepend to keys.
    :param delim: The delimiter string to separate keys.
    :return: A flat dictionary.
    """
    result: Dict[str, Any] = {}

    for key, value in data.items():
        full_key = f"{prefix}{delim}{key}" if prefix else key

        if isinstance(value, dict):
            result.update(flatten_dict(value, full_key, delim))
        elif isinstance(value, list):
            for i, el in enumerate(value):
                if isinstance(el, dict):
                    result.update(
                        flatten_dict(
                            cast(Dict[str, Any], el), f"{full_key}#{i + 1}", delim
                        )
                    )
                else:
                    result[f"{full_key}#{i + 1}"] = el
        else:
            result[full_key] = value

    return result


def _parse_index(head: str) -> Tuple[bool, str, int]:
    tokens = head.split("#")
    if len(tokens) > 1 and tokens[-1].isdigit():
        return True, "#".join(tokens[:-1]), int(tokens[-1])
    return False, head, 0


def _unflatten_value(
    out_dict: Dict[str, Union[Dict, List, Any]], key: Deque[str], value: Any
) -> None:
    head = key.popleft()
    tail = key
    is_index, head, index = _parse_index(head)
    if tail:
        if is_index:
            if head not in out_dict:
                out_dict[head] = []
            el = out_dict[head]
            assert isinstance(el, list)
            while index > len(el):
                el.append({})
            next_el = el[index - 1]
            assert isinstance(next_el, dict)
            _unflatten_value(next_el, tail, value)
        else:
            if head not in out_dict:
                out_dict[head] = {}
            el = out_dict[head]
            assert isinstance(el, dict)
            _unflatten_value(el, tail, value)
    else:
        out_dict[head] = value


def unflatten_dict(in_dict: Dict[str, Any]) -> Dict[str, Union[Dict, Any]]:
    out_dict: Dict[str, Union[Dict, List, Any]] = {}
    for key, value in in_dict.items():
        _unflatten_value(out_dict, deque(key.split(FLATTEN_DICT_DELIM)), value)
    return out_dict


def checked_get(data: Dict[str, Any], key, expected_type: Type, optional: bool = False):
    if key not in data:
        raise ValueError(f"Corrupted data - missing key {key}.")
    if data[key] is None:
        if optional:
            return None
        raise ValueError(f"Corrupted data - non-optional {key} is None.")
    if not isinstance(data[key], expected_type):
        type_name = type(data[key]).__name__
        expected_type_name = expected_type.__name__
        raise ValueError(
            f"Corrupted data - {key} has incorrect type {type_name}, expected "
            f"{expected_type_name}."
        )
    return data[key]


def _inline_meta(value: Any) -> Optional[str]:
    """VALUE on one line, or None if it needs a block of its own."""
    if isinstance(value, dict):
        if "min" in value and "max" in value:
            return f"[{value['min']}, {value['max']}]"
        return None
    if isinstance(value, list):
        if any(isinstance(item, (dict, list)) for item in value):
            return None
        return "[{}]".format(", ".join(str(item) for item in value))
    return str(value)


def _indent(lines: List[str], indent: str) -> List[str]:
    """LINES indented, leaving blank lines blank."""
    return [f"{indent}{line}" if line else "" for line in lines]


def _format_meta_block(value: Any) -> List[str]:
    """The lines of a VALUE that does not fit on one line.

    A dictionary becomes one element per entry, a list one dash per item.
    """
    if isinstance(value, dict):
        return [line for key, item in value.items() for line in format_meta(key, item)]
    lines = []
    for item in value:
        inline = _inline_meta(item)
        item_lines = (
            inline.split("\n") if inline is not None else _format_meta_block(item)
        ) or [""]
        lines.append(f"- {item_lines[0]}")
        lines.extend(_indent(item_lines[1:], "  "))
    return lines


def format_meta(name: str, value: Any) -> List[str]:
    """The lines showing the metadata element NAME with its VALUE.

    A scalar, a range or a flat list follows the name on its line, with any
    further lines of a multi-line string aligned under the first. A nested
    dictionary or list is indented below the name.
    """
    inline = _inline_meta(value)
    if inline is None:
        return [f"{name}:", *_indent(_format_meta_block(value), "  ")]
    first, *rest = inline.split("\n")
    return [f"{name}: {first}", *_indent(rest, " " * (len(name) + 2))]
