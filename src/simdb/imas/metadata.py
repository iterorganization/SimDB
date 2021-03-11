import os
import yaml
from typing import Dict, Any, List
from pathlib import Path
from enum import Enum

from .utils import is_missing


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


def walk_imas(imas_obj) -> Dict:
    meta = {}
    for name in (i for i in dir(imas_obj) if not i.startswith('_')):
        attr = getattr(imas_obj, name)
        meta[name] = {}
        if 'numpy.ndarray' in str(type(attr)):
            if attr.size != 0:
                meta[name] = attr
        if type(attr) == int:
            if attr != -999999999:
                meta[name] = attr
        if type(attr) == str:
            if attr:
                meta[name] = attr
        if type(attr) == float:
            if attr != -9e+40:
                meta[name] = attr
        elif '__structure' in str(type(attr)):
            meta[name] = walk_imas(attr)
    return meta


def walk_dict(d: Dict, imas_obj, depth: int, read_values: ReadValues) -> Dict:
    meta = {}
    for (k, v) in d.items():
        if depth == 0:
            getattr(imas_obj, k).get()
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
                meta[k][metric] = fetch_metric(metric, imas_obj)
        elif v == 'value' or (read_values == ReadValues.ALL and k != 'values'):
            if k not in meta:
                meta[k] = {}
            meta[k] = getattr(imas_obj, k)

            if read_values == ReadValues.ALL:
                meta[k] = walk_imas(imas_obj)
        elif k != 'values':
            child = getattr(imas_obj, k)
            if 'structArray' in type(child).__name__:
                values = []
                for (i, el) in enumerate(child):
                    values.append(walk_dict(d[k], el, depth + 1, read_values))
                meta[k] = values
            else:
                meta[k] = walk_dict(d[k], child, depth + 1, read_values)
    if read_values == ReadValues.ALL:
        return walk_imas(imas_obj)
    return meta


def load_metadata(imas_obj):
    with open(Path(__file__).absolute().parent / 'imas_metadata.yaml') as f:
        text = f.read()

    data = yaml.safe_load(text)
    meta = walk_dict(data, imas_obj, 0, ReadValues.SELECTED)
    return meta


def list_idss(imas_obj) -> List[str]:
    idss = []
    for name in (i for i in dir(imas_obj) if not i.startswith('_')):
        if '%s.%s' % (name, name) in str(type(getattr(imas_obj, name))):
            ids = getattr(imas_obj, name)
            ids.get()
            if not is_missing(ids.ids_properties.homogeneous_time):
                idss.append(name)
    return idss
