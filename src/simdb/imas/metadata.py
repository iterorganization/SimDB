from typing import Dict, Any
from enum import Enum


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
        raise MetricException(ex)


class ReadValues(Enum):
    ALL = 1
    SELECTED = 2


def walk_imas(ids_node) -> Dict:
    import imas

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
            meta[k] = walk_dict(d[k], ids, depth + 1, read_values)
            continue

        if k == "values":
            try:
                read_values = ReadValues[v.upper()]
            except KeyError:
                raise ValueError(
                    "Invalid values option: %s (valid options are [%s])"
                    % (v, ", ".join(i.name.lower() for i in ReadValues))
                )
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
                for i, el in enumerate(child):
                    values.append(walk_dict(d[k], el, depth + 1, read_values))
                meta[k] = values
            else:
                meta[k] = walk_dict(d[k], child, depth + 1, read_values)
    if read_values == ReadValues.ALL:
        return walk_imas(node)
    return meta


def load_metadata(entry):
    # with open(Path(__file__).absolute().parent / 'imas_metadata.yaml') as f:
    #     text = f.read()
    #
    # data = yaml.safe_load(text)
    data_to_read = {
        "summary": {
            "values": "all",
        },
        # "dataset_description": {
        #     "values": "all",
        # },
    }
    meta = walk_dict(data_to_read, entry, 0, ReadValues.SELECTED)
    return meta
