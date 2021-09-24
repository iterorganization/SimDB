# -*- coding: utf-8 -*-
"""SimDB.

SimDB is the ITER simulation database management tool designed to track, manage and validate simulations and allow for
these simulations to be sent for remote archiving and verification.

The tool comes in two parts:
    * The command line interface (CLI) tool which users can run on the command line to add, edit, view and query
      stored simulations.
    * The remote REST API which is run in a centralised location to allow the users simulations to be pushed for
      staging and checking.
"""

import pkg_resources
from typing import Tuple, cast

__version__: str = pkg_resources.require("simdb")[0].version
__version_info__: Tuple[str, str, str] = cast(Tuple[str, str, str], tuple(__version__.split('.')))
try:
    __licence__: str = pkg_resources.require("simdb")[0].get_metadata('LICENCE')
except FileNotFoundError:
    # When installing with 'pip -e' in development environment
    __licence__: str = "see LICENCE"
