#!/bin/sh
# Set up ITER modules environment
set -e

# Set up environment
. /usr/share/Modules/init/sh

module use /work/imas/etc/modules/all
module purge
module load Python/3.8.6-GCCcore-10.2.0
module list

# Set up virtualenv
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip3 install --upgrade pip
pip3 install pytest pytest-cov wheel cobertura-clover-transform
pip3 install -r dev_requirements.txt
pip3 install easyad

# Install simdb
pip3 install .

# Run the tests
python3 -m pytest --cov=simdb --junitxml=test-reports/pytest.xml

# Generate coverage report
# coverage html -d simdb-coverage-report
# tar czf simdb-coverage-report.tar.gz simdb-coverage-report/

# coverage xml
# cobertura-clover-transform coverage.xml -o clover.xml
