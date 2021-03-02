import os
from typing import List, Dict, Any, Union, Tuple
from sqlalchemy.ext.declarative import declarative_base


def _flatten_dict(out_dict: Dict[str, str], in_dict: Dict[str, Union[Dict, List, Any]], prefix: Tuple=()):
    for key, value in in_dict.items():
        if isinstance(value, dict):
            _flatten_dict(out_dict, value, prefix + (key,))
        elif isinstance(value, list):
            for el in value:
                _flatten_dict(out_dict, {key: el}, prefix)
        else:
            out_dict['.'.join(prefix + (key,))] = str(value)


class BaseModel:
    """
    Base model for ORM classes.
    """
    def __str__(self):
        """
        Return a string representation of the {cls.__name__} formatted to print.

        :return: The {cls.__name__} as a string for printing.
        """
        raise NotImplementedError

    @classmethod
    def from_data(cls, data: Dict) -> "BaseModel":
        """
        Create a Model from serialised data.

        :param data: Serialised model data.
        :return: The created model.
        """
        raise NotImplementedError

    def data(self, recurse: bool=False) -> Dict:
        """
        Serialise the {cls.__name__}.

        :param recurse: If True also serialise any contained models, otherwise only serialise simple fields.
        :return: The serialised data.
        """
        raise NotImplementedError


Base: Any = declarative_base(cls=BaseModel)


def _get_imas_paths(imas: Dict) -> List[str]:
    if "IMAS_VERSION" not in os.environ:
        raise Exception("$IMAS_VERSION not defined")
    imas_version = os.environ["IMAS_VERSION"]
    imas_file_base = "ids_%d%04d" % (imas["shot"], imas["run"])
    if "path" in imas:
        path = os.path.join(imas["path"], imas_version.split(".")[0], "0")
    else:
        if "MDSPLUS_TREE_BASE_0" not in os.environ:
            raise Exception("path not specified for IDS and $MDSPLUS_TREE_BASE_0 not defined")
        path = os.environ["MDSPLUS_TREE_BASE_0"]
    return [
        os.path.join(path, imas_file_base + ".characteristics"),
        os.path.join(path, imas_file_base + ".datafile"),
        os.path.join(path, imas_file_base + ".tree"),
    ]
