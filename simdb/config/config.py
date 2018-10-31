import configparser
import appdirs
import os
from typing import Tuple, List, Optional

from .. import __version__


def _parser_arg(arg) -> Tuple[str, str]:
    if '-' in arg:
        section, option = arg.split('-', 1)
    else:
        section = 'DEFAULT'
        option = arg
    return section, option


class Config:

    CONFIG_FILE_NAME: str = 'simdb.cfg'

    def __init__(self) -> None:
        self._parser: configparser.ConfigParser = configparser.ConfigParser()
        self._site_config_dir: str = appdirs.site_config_dir('simdb')
        self._site_config_file: str = os.path.join(self._site_config_dir, Config.CONFIG_FILE_NAME)
        self._user_config_dir: str = appdirs.user_config_dir('simdb')
        self._user_config_file: str = os.path.join(self._user_config_dir, Config.CONFIG_FILE_NAME)

    def load(self) -> None:
        if os.path.exists(self._site_config_file):
            with open(self._site_config_file) as file:
                self._parser.read_file(file)

        if os.path.exists(self._user_config_file):
            with open(self._user_config_file) as file:
                self._parser.read_file(file)

        self.api_version = __version__

    def save(self) -> None:
        os.makedirs(self._user_config_dir, exist_ok=True)
        with open(self._user_config_file, 'w') as file:
            self._parser.write(file)

    def get_option(self, name: str, default: Optional[str]=None) -> str:
        section, option = _parser_arg(name)
        try:
            return self._parser.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if default is not None:
                return default
            raise ValueError(name + ' not found in configuration')

    def set_option(self, name: str, value: str) -> None:
        section, option = _parser_arg(name)
        if not self._parser.has_section(section):
            self._parser.add_section(section)
        self._parser.set(section, option, value)
        self.save()

    def list_options(self) -> List[str]:
        options = []
        for section in self._parser.sections():
            for option in self._parser.options(section):
                value = self._parser.get(section, option)
                if section == 'DEFAULT':
                    options.append('%s: %s' % (option, value))
                else:
                    options.append('%s-%s: %s' % (section, option, value))
        return options
