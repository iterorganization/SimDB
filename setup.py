import setuptools
import os
import versioneer

with open("README.md", "r") as fh:
    long_description = fh.read()


setuptools.setup(
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(), 
)
