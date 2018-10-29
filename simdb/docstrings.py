def inherit_docstrings(cls):
    from inspect import getmembers, isfunction

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
