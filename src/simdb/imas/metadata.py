import os
import yaml
from typing import Dict, Any
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


def walk_imas(imas_obj) -> Dict:
    meta = {}
    for name in (i for i in dir(imas_obj) if not i.startswith('_')):
        attr = getattr(imas_obj, name)
        if str(type(attr)) == 'numpy.ndarray':
            if attr.size != 0:
                meta[name]['value'] = attr
        if type(attr) == int:
            if attr != -999999999:
                meta[name]['value'] = attr
        if type(attr) == str:
            if attr:
                meta[name]['value'] = attr
        if type(attr) == float:
            if attr != -9e+40:
                meta[name]['value'] = attr
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
        elif v == 'value' or read_values == ReadValues.ALL:
            if k not in meta:
                meta[k] = {}
            meta[k]['value'] = getattr(imas_obj, k)

            if read_values == ReadValues.ALL:
                walk_imas(imas_obj)
        else:
            child = getattr(imas_obj, k)
            if 'structArray' in type(child).__name__:
                values = []
                for (i, el) in enumerate(child):
                    values.append(walk_dict(d[k], el, depth + 1, read_values))
                meta[k] = values
            else:
                meta[k] = walk_dict(d[k], child, depth + 1, read_values)
    if read_values == ReadValues.ALL:
        walk_imas(imas_obj)
    return meta


def load_metadata(shot, run):
    import imas
    imas_obj = imas.ids(shot, run)
    imas_obj.open_env(os.environ['USER'], 'iter', '3')

    with open(Path(__file__).absolute().parent / 'imas_metadata.yaml') as f:
        text = f.read()

    data = yaml.safe_load(text)
    meta = walk_dict(data, imas_obj, 0, ReadValues.SELECTED)
    return meta


def check_ids(imas_obj):
    for name in (i for i in dir(imas_obj) if not i.startswith('_')):
        if '%s.%s' % (name, name) in str(type(getattr(imas_obj, name))):
            pass
