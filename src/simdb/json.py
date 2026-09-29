import base64
import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict

import numpy as np

from simdb.remote.models import RangeValue

if TYPE_CHECKING:
    import json
else:
    try:
        import simplejson as json
    except ImportError:
        import json


def _custom_hook(obj: Dict[str, str]) -> Any:
    if "_type" in obj:
        if obj["_type"] == "uuid.UUID":
            return uuid.UUID(obj["hex"])
        elif obj["_type"] == "numpy.ndarray":
            np_bytes = base64.decodebytes(obj["bytes"].encode())
            return np.frombuffer(np_bytes, dtype=obj["dtype"])
        else:
            obj_type = obj["_type"]
            raise ValueError(f"Unknown type to deserialise {obj_type}.")
    return obj


class CustomDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        kwargs["object_hook"] = _custom_hook
        super().__init__(*args, **kwargs)


class CustomEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        kwargs["allow_nan"] = False
        if json.__name__ == "simplejson":
            kwargs["ignore_nan"] = True
        super().__init__(*args, **kwargs)

    def default(self, o: Any) -> Any:
        if isinstance(o, RangeValue):
            return {"min": o.min, "max": o.max}
        elif isinstance(o, uuid.UUID):
            return {"_type": "uuid.UUID", "hex": o.hex}
        elif isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()
        elif isinstance(o, enum.Enum):
            return o.value
        elif isinstance(o, np.ndarray):
            if np.issubdtype(o.dtype, np.number):
                valid = o[~np.isnan(o)] if np.issubdtype(o.dtype, np.floating) else o
                return {"min": float(valid.min()), "max": float(valid.max())}
            return o.tolist()
        return super().default(o)
