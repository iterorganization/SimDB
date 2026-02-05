import os
import platform
from pathlib import Path
from typing import Dict, List, NewType, Union

import click
import distro
import yaml

PlatformDetails = NewType("PlatformDetails", Dict[str, str])
EnvironmentDetails = NewType("EnvironmentDetails", Dict[str, Union[str, List[str]]])


def _platform_version() -> str:
    return distro.name(pretty=True)


def _platform_details() -> PlatformDetails:
    data = PlatformDetails(
        {
            "architecture": " ".join(platform.architecture()),
            "libc_ver": " ".join(platform.libc_ver()),
            "machine": platform.machine(),
            "node": platform.node(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "release": platform.release(),
            "system": platform.system(),
            "os_version": _platform_version(),
        }
    )
    return data


def _environmental_vars() -> EnvironmentDetails:
    env_vars = EnvironmentDetails({})
    for k, v in os.environ.items():
        if "PATH" in k:
            env_vars[k] = [i for i in v.split(os.pathsep) if i]
        else:
            env_vars[k] = v
    return env_vars


def _get_provenance() -> Dict[str, Union[PlatformDetails, EnvironmentDetails]]:
    prov: Dict[str, Union[PlatformDetails, EnvironmentDetails]] = {
        "environment": _environmental_vars(),
        "platform": _platform_details(),
    }
    return prov


@click.command("provenance")
@click.argument("provenance_file", type=click.Path())
def provenance(provenance_file):
    """Create the PROVENANCE_FILE from the current system."""

    provenance_file = Path(provenance_file)

    with provenance_file.open("w") as file:
        yaml.dump(_get_provenance(), file, default_flow_style=False)

    click.echo(f"Create provenance file {provenance_file}.")
