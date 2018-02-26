from inspect import getmembers, isfunction
import hashlib


def inherit_docstrings(cls):
    for name, func in getmembers(cls, isfunction):
        if func.__doc__:
            continue
        for parent in cls.__mro__[1:]:
            if hasattr(parent, name):
                func.__doc__ = getattr(parent, name).__doc__.format(cls=cls)
    return cls


def format_docstring(cls):
    def decorator(func):
        func.__doc__ = func.__doc__.format(cls=cls)
        return func
    return decorator


def sha1_checksum(path: str) -> str:
    sha1 = hashlib.sha1()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha1.update(chunk)
    return sha1.hexdigest()