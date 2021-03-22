#!/bin/bash

# Run sphinx-apidoc to generate the latest documentation from the SimDB codebase.

sphinx-apidoc -f -o sphinx -e -M ../src/simdb && rm modules.rst
