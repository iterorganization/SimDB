import configparser

import appdirs
import os
from pathlib import Path
from typing import Tuple, List, Optional, TextIO, Union, Dict, cast


class ConfigError(Exception):
    pass


def _parse_name(arg: str) -> Tuple[str, str]:
    if "." in arg:
        section, *name, option = arg.split(".")
        if name:
            section = '{} "{}"'.format(section, ".".join(name))
    else:
        section = "DEFAULT"
        option = arg
    return section, option


def _parse_section(arg: str) -> str:
    if "." in arg:
        section, *name = arg.split(".")
        if name:
            section = '{} "{}"'.format(section, ".".join(name))
    else:
        section = arg
    return section


def _isdecimal(v: str):
    return len(v) == 0 or v.isdecimal()


def _isfloat(value: str) -> bool:
    l, *r = value.split(".")
    return _isdecimal(l) and (len(r) == 0 or (len(r) == 1 and _isdecimal(r[0])))


def _convert(value: str) -> Union[int, float, str, bool]:
    if value == "":
        return value
    elif value.isdecimal():
        return int(value)
    elif _isfloat(value):
        return float(value)
    elif value.lower() in configparser.ConfigParser.BOOLEAN_STATES:
        return configparser.ConfigParser.BOOLEAN_STATES[value.lower()]
    else:
        return value


class Config:
    class _NothingSentinel:
        pass

    NOTHING = _NothingSentinel()
    CONFIG_FILE_NAME: str = "simdb.cfg"

    _parser: configparser.ConfigParser
    _site_config_dir: Path
    _site_config_path: Path
    _user_config_dir: Path
    _user_config_path: Path
    _api_version: str
    _debug: bool
    _verbose: bool

    def __init__(self, file_name=None) -> None:
        if file_name is None:
            file_name = Config.CONFIG_FILE_NAME
        self._parser = configparser.ConfigParser()
        self._site_config_dir = Path(appdirs.site_config_dir("simdb"))
        self._site_config_path = self._site_config_dir / file_name
        self._user_config_dir = Path(appdirs.user_config_dir("simdb"))
        self._user_config_path = self._user_config_dir / file_name
        self._api_version = "1.2"
        self._debug = False
        self._verbose = False

    @property
    def user_config_path(self) -> Path:
        return self._user_config_path

    def _load_environmental_vars(self):
        vars = [v for v in os.environ if v.startswith("SIMDB_")]
        for var in vars:
            name = var.replace("SIMDB_", "").replace("_", ".").lower()
            self.set_option(name, os.environ[var])

    def _load_site_config(self):
        self._parser.read(self._site_config_path)

    def _load_user_config(self):
        if (
            self._user_config_path.exists()
            and self._user_config_path.stat().st_mode != 0o100600
        ):
            raise Exception(
                f"""
User configuration file {self._user_config_path} has incorrect permissions (must have 0600 permissions).
            """
            )
        self._parser.read(self._user_config_path)

    @property
    def api_version(self) -> str:
        return self._api_version

    def load(self, file: Optional[TextIO] = None) -> None:
        """
        Load the configuration.

        This loads the configuration from the given file and the site config and user config files.

        The location of these files are either specified by SIMDB_USER_CONFIG_PATH and
        SIMDB_SITE_CONFIG_PATH environmental variables or in the appdirs.site_config_dir('simdb') and
        appdirs.user_config_dir('simdb').

        The user config file is loaded after the site config file and will overwrite any settings specified. The given
        file is loaded after both the site and user config files.

        :param file: The location of a config file to load.
        """
        self._load_environmental_vars()

        # Import configuration options from files defined by environment variables
        path = self.get_string_option("user.config-path", default="")
        if path:
            self._user_config_path = Path(path)
            self._user_config_dir = self._user_config_path.parent

        path = self.get_string_option("site.config-path", default="")
        if path:
            self._site_config_path = Path(path)
            self._site_config_dir = self._site_config_path.parent

        if file is not None:
            name = file.name if hasattr(file, "name") else "-"
            self._user_config_path = Path(name)
            self._parser.read_file(file)
        else:
            self._load_site_config()
            self._load_user_config()

    @property
    def debug(self) -> bool:
        """
        Returns the debug status flag.
        """
        return self._debug

    @debug.setter
    def debug(self, debug: bool) -> None:
        """
        Set the debug status flag.
        """
        self._debug = debug

    @property
    def default_remote(self) -> Optional[str]:
        """
        Returns the default remote used by the SimDB client.
        """
        remotes = [
            section
            for section in self._parser.sections()
            if section.startswith("remote")
        ]
        for remote in remotes:
            if self._parser.getboolean(remote, "default", fallback=False):
                return remote.split(" ")[1][1:-1]
        return None

    @default_remote.setter
    def default_remote(self, default: str):
        """
        Set the default remote used by the SimDB client.
        """
        remotes = [
            section
            for section in self._parser.sections()
            if section.startswith("remote")
        ]
        found = False
        for remote in remotes:
            name = remote.split(" ")[1][1:-1]
            self._parser.set(remote, "default", str(name == default))
            if name == default:
                found = True
        if not found:
            raise KeyError(f"remote {default} not found in configuration.")

    @property
    def config_directory(self) -> Path:
        """
        Returns the directory that the local user configuration file is loaded from.
        @return:
        """
        return self._user_config_dir

    @property
    def verbose(self) -> bool:
        """
        Returns the SimDB client verbosity flag.
        """
        return self._verbose

    @verbose.setter
    def verbose(self, verbose: bool) -> None:
        """
        Sets the SimDB client verbosity flag.
        """
        self._verbose = verbose

    def save(self) -> None:
        """
        Save the current state of the configuration to a configuration file in the users configuration directory.
        """
        os.makedirs(self._user_config_dir, exist_ok=True)
        os.umask(0)
        descriptor = os.open(
            path=self._user_config_path,
            flags=os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            mode=0o600,
        )
        with open(descriptor, "w") as file:
            self._parser.write(file)

    def sections(self) -> List[str]:
        """
        Return all sections in the configuration.
        """
        return self._parser.sections()

    def get_section(
        self,
        name: str,
        default: Optional[Dict[str, Union[int, float, bool, str]]] = None,
    ) -> Dict[str, Union[int, float, bool, str]]:
        """
        Returns the section from the configuration with the given name.

        @param name: the name of the section to find
        @param default: a dictionary that will be returned if the section is not found
        @return: the section corresponding to the given name, or the default if given and the section is not found
        @raise KeyError if the section is not found and no default is given
        """
        try:
            items = self._parser.items(name)
            return {k: _convert(v) for (k, v) in items}
        except (configparser.NoSectionError,):
            if default is not None:
                return default
            raise KeyError(f"Section {name} not found in configuration")

    def get_option(
        self, name: str, default: Union[int, float, bool, str, None, _NothingSentinel] = NOTHING
    ) -> Union[int, float, bool, str]:
        """
        Returns the value for the option with the given name from the configuration.

        @param name: the name of the option to return
        @param default: the value to return if the option is not found in the configuration
        @return: the value of the found option, or the default if given and the option is not found
        @raise KeyError if the option is not found and no default is given
        """
        section, option = _parse_name(name)
        try:
            return _convert(self._parser.get(section, option))
        except (configparser.NoSectionError, configparser.NoOptionError):
            if default is not Config.NOTHING:
                value = cast(Union[int, float, bool, str], default)
                return value
            raise KeyError(f"Option {name} not found in configuration")

    def get_string_option(self, name: str, default: Union[str, None, _NothingSentinel] = NOTHING) -> str:
        """
        Returns the value for the option with the given name from the configuration but also ensures the resulting
        value is a string.

        @see get_option
        @raise TypeError if the found value was not a string
        """
        value = self.get_option(name, default)
        if not isinstance(value, str):
            raise TypeError(f"Invalid type of option {name}: expected str, got {type(value)}")
        return value

    def delete_option(self, name: str) -> None:
        """
        Delete the option with the given name from the configuration.

        @param name: the name of the option to delete
        """
        section, option = _parse_name(name)
        try:
            self._parser.remove_option(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            raise KeyError(f"Option {name} not found in configuration")

    def delete_section(self, name: str) -> None:
        """
        Delete the section with the given name from the configuration.

        This will also delete all options contained in this section.

        @param name: the name of the section to delete
        """
        section = _parse_section(name)
        try:
            self._parser.remove_section(section)
        except configparser.NoSectionError:
            raise KeyError(f"Section {name} not found in configuration")

    def set_option(self, name: str, value: Union[int, float, bool, str]) -> None:
        """
        Set the option with the given name to the given value.

        @param name: the name of the option to set
        @param value: the value to set the option to
        """
        section, option = _parse_name(name)
        if not self._parser.has_section(section) and section != "DEFAULT":
            self._parser.add_section(section)
        self._parser.set(section, option, str(value))

    def list_options(self) -> List[str]:
        """
        List all the options found in the configuration.

        @return: the values found as a list of "name: value" strings
        """
        options = []
        for section in self._parser.sections():
            for option in self._parser.options(section):
                value = self._parser.get(section, option)
                if section == "DEFAULT":
                    options.append(f"{option}: {value}")
                else:
                    sec_name, *name = section.split(" ")
                    if name:
                        sec_name = sec_name + "." + name[0][1:-1]
                    options.append(f"{sec_name}.{option}: {value}")
        return options
