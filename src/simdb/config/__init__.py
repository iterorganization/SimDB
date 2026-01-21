"""Config module.

The config module contains the code for reading the global and user configuration files which are used to populate
the Config object passed to other parts of SimDB.
"""

from .config import Config, ConfigError

__all__ = ["Config", "ConfigError"]
