import re
from enum import Enum
from typing import Any, Dict

import imas
import imas.dd_zip
import imas.ids_defs
from semantic_version import Version

from simdb.remote.models import _array_to_range


class MetricException(Exception):
    pass


def fetch_metric(metric: str, imas_obj) -> Any:
    metrics = {
        "len": lambda x: len(x),
        "max": lambda x: max(x),
        "min": lambda x: min(x),
    }
    try:
        return metrics[metric](imas_obj)
    except Exception as ex:
        raise MetricException() from ex


class ReadValues(Enum):
    ALL = 1
    SELECTED = 2


def walk_imas(ids_node) -> Dict:
    meta = {}
    for name in (i for i in dir(ids_node) if not i.startswith("_")):
        attr = getattr(ids_node, name)
        meta[name] = {}
        if "numpy.ndarray" in str(type(attr)):
            if attr.size != 0:
                meta[name] = attr
        elif isinstance(attr, int):
            if attr != imas.ids_defs.EMPTY_INT:
                meta[name] = attr
        elif isinstance(attr, str):
            if attr:
                meta[name] = attr
        elif isinstance(attr, float):
            if attr != imas.ids_defs.EMPTY_FLOAT:
                meta[name] = attr
        elif "__structure" in str(type(attr)):
            meta[name] = walk_imas(attr)
        elif "__structArray" in str(type(attr)):
            values = []
            for el in attr:
                values.append(walk_imas(el))
            meta[name] = values
    return meta


def walk_dict(d: Dict, node, depth: int, read_values: ReadValues) -> Dict:
    meta = {}
    for k, v in d.items():
        if depth == 0:
            ids = node.get(k)
            meta[k] = walk_dict(v, ids, depth + 1, read_values)
            continue

        if k == "values":
            try:
                read_values = ReadValues[v.upper()]
            except KeyError:
                raise ValueError(
                    "Invalid values option: {} (valid options are [{}])".format(
                        v, ", ".join(i.name.lower() for i in ReadValues)
                    )
                ) from None
        if k == "metrics":
            if k not in meta:
                meta[k] = {}
            for metric in v:
                meta[k][metric] = fetch_metric(metric, node)
        elif v == "value" or (read_values == ReadValues.ALL and k != "values"):
            if k not in meta:
                meta[k] = {}
            meta[k] = getattr(node, k)

            if read_values == ReadValues.ALL:
                meta[k] = walk_imas(node)
        elif k != "values":
            child = getattr(node, k)
            if "structArray" in str(type(child)):
                values = []
                for _i, el in enumerate(child):
                    values.append(walk_dict(v, el, depth + 1, read_values))
                meta[k] = values
            else:
                meta[k] = walk_dict(v, child, depth + 1, read_values)
    if read_values == ReadValues.ALL:
        return walk_imas(node)
    return meta


def extract_ids_path(coords_str: str) -> str:
    """Extract path from IDSCoordinates string representation"""
    # Check if string matches expected format
    if not coords_str.startswith(
        "<IDSCoordinates of '"
    ):  # or not coords_str.endswith("'>")
        return ""

    path_match = re.search(r"'([^']+)'", coords_str)
    path = path_match.group(1) if path_match else ""
    return path


def load_imas_metadata(ids_dist, entry) -> dict:
    """
    Load metadata from IMAS entry.
    :param ids_list: Dictionary where keys are IDS names and values are configurations.
    :param entry: IMAS entry object.
    :return: Dictionary containing metadata.
    """

    latest_dd_version = imas.dd_zip.latest_dd_version()
    if latest_dd_version is None:
        raise RuntimeError("Could not determine the data dictionary version.")

    try:
        parsed_dd_version = Version(latest_dd_version)
    except ValueError as exc:
        raise RuntimeError(
            f"Could not parse the data dictionary version: {latest_dd_version!r}."
        ) from exc

    dd_major_version = parsed_dd_version.major
    if not isinstance(dd_major_version, int):
        raise RuntimeError(
            f"Could not determine the major data dictionary version from "
            f"{latest_dd_version!r}."
        )

    if dd_major_version > 4:
        raise RuntimeError(
            f"Unsupported data dictionary version {latest_dd_version!r}: "
        )

    metadata = {"metadata_dd_version": latest_dd_version}
    for ids_name, _v in ids_dist.items():
        ids = entry.get(ids_name, autoconvert=False)
        ids = imas.convert_ids(ids, latest_dd_version)
        for node in imas.util.tree_iter(ids):
            metadata[extract_ids_path(str(node.coordinates)).replace("/", ".")] = (  # type: ignore
                _array_to_range(node.value)  # type: ignore
            )
    return metadata


def load_metadata(entry):
    data_to_read = {
        "summary": {
            "values": "all",
        },
    }
    meta = load_imas_metadata(data_to_read, entry)
    return meta
