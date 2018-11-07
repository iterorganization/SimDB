#!/bin/bash

# Run sphinx-apidoc to generate the latest documentation from the SimDB codebase.

sphinx-apidoc -f -o . -e -M ../simdb && rm modules.rst
