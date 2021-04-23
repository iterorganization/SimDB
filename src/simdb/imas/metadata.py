import os
import yaml
from typing import Dict, Any, List
from pathlib import Path
from enum import Enum


class MetricException(Exception):
    pass


def fetch_metric(metric: str, imas_obj) -> Any:
    print(type(imas_obj))
    metrics = {
        'len': lambda x: len(x),
        'max': lambda x: max(x),
        'min': lambda x: min(x),
    }
    try:
        return metrics[metric](imas_obj)
    except Exception as ex:
        raise MetricException(ex)


class ReadValues(Enum):
    ALL = 1
    SELECTED = 2


def walk_imas(ids_node) -> Dict:
    import imasdef
    meta = {}
    for name in (i for i in dir(ids_node) if not i.startswith('_')):
        attr = getattr(ids_node, name)
        meta[name] = {}
        if 'numpy.ndarray' in str(type(attr)):
            if attr.size != 0:
                meta[name] = attr
        elif type(attr) == int:
            if attr != imasdef.EMPTY_INT:
                meta[name] = attr
        elif type(attr) == str:
            if attr:
                meta[name] = attr
        elif type(attr) == float:
            if attr != imasdef.EMPTY_FLOAT:
                meta[name] = attr
        elif '__structure' in str(type(attr)):
            meta[name] = walk_imas(attr)
        elif '__structArray' in str(type(attr)):
            values = []
            for el in attr:
                values.append(walk_imas(el))
            meta[name] = values
    return meta


def walk_dict(d: Dict, entry, depth: int, read_values: ReadValues) -> Dict:
    meta = {}
    ids = None
    for (k, v) in d.items():
        if depth == 0:
            ids = entry.get(k)
        if k == 'values':
            try:
                read_values = ReadValues[v.upper()]
            except KeyError:
                raise ValueError('Invalid values option: %s (valid options are [%s])'
                                 % (v, ', '.join(i.name.lower() for i in ReadValues)))
        if k == 'metrics':
            if k not in meta:
                meta[k] = {}
            for metric in v:
                meta[k][metric] = fetch_metric(metric, ids)
        elif v == 'value' or (read_values == ReadValues.ALL and k != 'values'):
            if k not in meta:
                meta[k] = {}
            meta[k] = getattr(ids, k)

            if read_values == ReadValues.ALL:
                meta[k] = walk_imas(ids)
        elif k != 'values':
            child = getattr(ids, k)
            if 'structArray' in type(child).__name__:
                values = []
                for (i, el) in enumerate(child):
                    values.append(walk_dict(d[k], el, depth + 1, read_values))
                meta[k] = values
            else:
                meta[k] = walk_dict(d[k], child, depth + 1, read_values)
    if read_values == ReadValues.ALL:
        return walk_imas(ids)
    return meta


def load_metadata(entry):
    with open(Path(__file__).absolute().parent / 'imas_metadata.yaml') as f:
        text = f.read()

    data = yaml.safe_load(text)
    meta = walk_dict(data, entry, 0, ReadValues.SELECTED)
    return meta
