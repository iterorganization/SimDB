import os
import yaml
import platform
from typing import Dict, Union, List, NewType


PlatformDetails = NewType('PlatformDetails', Dict[str, str])
EnvironmentDetails = NewType('EnvironmentDetails', Dict[str, Union[str, List[str]]])


def _platform_version() -> str:
    if platform.system() == 'Linux':
        return ' '.join(platform.linux_distribution()) + ' ' + platform.version()
    elif platform.system() == 'Darwin':
        return platform.mac_ver()[0] + ' ' + platform.version()
    elif platform.system() == 'Win':
        return ' '.join(platform.win32_ver())
    return 'Unknown'


def _platform_details() -> PlatformDetails:
    """

    :return:
    """
    data = PlatformDetails(dict(
        architecture=' '.join(platform.architecture()),
        libc_ver=' '.join(platform.libc_ver()),
        machine=platform.machine(),
        node=platform.node(),
        platform=platform.platform(),
        processor=platform.processor(),
        python_version=platform.python_version(),
        release=platform.release(),
        system=platform.system(),
        os_version=_platform_version()
    ))
    return data


def _environmental_vars() -> EnvironmentDetails:
    env_vars = EnvironmentDetails({})
    for (k, v) in os.environ.items():
        if 'PATH' in k:
            env_vars[k] = [i for i in v.split(os.pathsep) if i]
        else:
            env_vars[k] = v
    return env_vars


def _get_provenance() -> Dict[str, Union[PlatformDetails, EnvironmentDetails]]:
    prov: Dict[str, Union[PlatformDetails, EnvironmentDetails]] = dict(
        environment=_environmental_vars(),
        platform=_platform_details(),
    )
    return prov


def create_provenance_file(file_name: str) -> None:
    """Extract all the provenance for the current machine node and write this into a YAML file with the given file
    name.

    This makes use of the Python platform library to extract OS and hardware information.

    :param file_name: The name of the file to store the provenance YAML in.
    """
    with open(file_name, 'w') as file:
        yaml.dump(_get_provenance(), file, default_flow_style=False)


def read_provenance_file(file_name: str) -> Union[Dict, List, None]:
    """Read the given provenance YAML file and return the read data.

    :param file_name: The name of the file to read.
    :return: The YAML provenance data.
    """
    with open(file_name, 'r') as file:
        return yaml.load(file)
