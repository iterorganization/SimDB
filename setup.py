import setuptools
import os

with open("README.md", "r") as fh:
    long_description = fh.read()


# version read from easybuild when not installed from git repo
version = os.environ.get('EBVERSIONSIMDB', '0.0.1')


setuptools.setup(
    version_config={
        'version_callback': version,
        'template': '{tag}',
        'dev_template': '{tag}.{ccount}',
        'dirty_template': '{tag}.{ccount}-dirty',
    },
)
