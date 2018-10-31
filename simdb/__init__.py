import os

__version__ = "0.1.1"

dir_path = os.path.dirname(os.path.realpath(__file__))
__licence__ = open(os.path.join(dir_path, "LICENCE.txt")).read()

del dir_path
del os