import os
import yaml
from typing import Dict, Any
from pathlib import Path


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


def walk_dict(d: Dict, imas_obj) -> Dict:
    meta = {}
    for (k, v) in d.items():
        if k == 'metrics':
            if k not in meta:
                meta[k] = {}
            for metric in v:
                meta[k][metric] = fetch_metric(metric, imas_obj)
        elif v == 'value':
            if k not in meta:
                meta[k] = {}
            meta[k]['value'] = getattr(imas_obj, k)
        else:
            child = getattr(imas_obj, k)
            if 'structArray' in type(child).__name__:
                values = []
                for (i, el) in enumerate(child):
                    values.append(walk_dict(d[k], el))
                meta[k] = values
            else:
                meta[k] = walk_dict(d[k], child)
    return meta


def load_metadata(shot, run):
    import imas
    imas_obj = imas.ids(shot, run)
    imas_obj.open_env(os.environ['USER'], 'iter', '3')
    imas_obj.magnetics.get()

    with open(Path(__file__).absolute().parent / 'imas_metadata.yaml') as f:
        text = f.read()

    data = yaml.safe_load(text)
    meta = walk_dict(data, imas_obj)
    return meta
