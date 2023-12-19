import os

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()
    
import sys

sys.path.append(os.getcwd())
import versioneer

setuptools.setup(
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(), 
)
