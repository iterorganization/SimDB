import os
import yaml
import platform
from typing import Dict, Union, List


def platform_version() -> str:
    if platform.system() == 'Linux':
        return ' '.join(platform.linux_distribution()) + ' ' + platform.version()
    elif platform.system() == 'Darwin':
        return platform.mac_ver()[0] + ' ' + platform.version()
    elif platform.system() == 'Win':
        return ' '.join(platform.win32_ver())
    return 'Unknown'


def platform_details() -> Dict:
    data = dict(
        architecture=' '.join(platform.architecture()),
        libc_ver=' '.join(platform.libc_ver()),
        machine=platform.machine(),
        node=platform.node(),
        platform=platform.platform(),
        processor=platform.processor(),
        python_version=platform.python_version(),
        release=platform.release(),
        system=platform.system(),
        os_version=platform_version()
    )
    return data


def enironmental_vars() -> Dict:
    vars: Dict[str, Union[str, List[str]]] = {}
    for (k, v) in os.environ.items():
        if 'PATH' in k:
            vars[k] = [i for i in v.split(os.pathsep) if i]
        else:
            vars[k] = v
    return vars


def get_provenance() -> Dict:
    prov = dict(
        environment=enironmental_vars(),
        platform=platform_details()
    )
    return prov


def create_provenance_file(file_name: str) -> None:
    with open(file_name, 'w') as file:
        yaml.dump(get_provenance(), file, default_flow_style=False)


def read_provenance_file(file_name: str) -> Dict:
    with open(file_name, 'r') as file:
        return yaml.load(file)
