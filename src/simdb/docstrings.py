from inspect import getmembers, isfunction


def inherit_docstrings(cls):
    """
    Inherit method docstrings from parent classes.

    Class decorator which goes through all the methods defined on this class and if that
    method does not already have a docstring then looks for one on the same method in
    the parent class hierarchy.

    :param cls: The class to decorate
    :return: The decorated class
    """

    for name, func in getmembers(cls, isfunction):
        if func.__doc__:
            continue
        for parent in cls.__mro__[1:]:
            if hasattr(parent, name):
                func.__doc__ = getattr(parent, name).__doc__.format(cls=cls)
    return cls
