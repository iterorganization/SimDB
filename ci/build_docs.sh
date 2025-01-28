#!/bin/bash
# Set up ITER modules environment
set -e

# Set up environment
if test -f /etc/profile.d/modules.sh ;then
. /etc/profile.d/modules.sh
else
. /usr/share/Modules/init/sh
fi

module use /work/imas/etc/modules/all
module purge
module load Python/3.11.5-GCCcore-13.2.0
module list

# Set up virtualenv
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip3 install --upgrade pip
pip3 install -r dev_requirements.txt

# Install simdb
pip3 install .

# Build docs
cd docs
sphinx-apidoc -f -o sphinx -e -M ../src/simdb && rm sphinx/modules.rst
cp *.md sphinx
cp *.svg sphinx
make clean
make html
mv _build/html/ ../html/
# cd ..
# tar czf html.tar.gz html/
