"""SimDB.

SimDB is the IMAS simulation database management tool designed to track, manage and validate simulations and allow for
these simulations to be sent for remote archiving and verification.

The tool comes in two parts:
    * The command line interface (CLI) tool which users can run on the command line to add, edit, view and query
      stored simulations.
    * The remote REST API which is run in a centralised location to allow the users simulations to be pushed for
      staging and checking.
"""

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

version = __version__
