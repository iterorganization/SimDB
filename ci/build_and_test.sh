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

# Upgrade pip and build tools
pip3 install --upgrade pip setuptools wheel

echo "Installing simdb with documentation dependencies..."

# Install build dependencies
pip3 install setuptools_scm

# Install simdb with test dependencies using pyproject.toml
pip3 install -e --group dev

echo "Checking version information..."
python3 -c "import simdb; print(f'SimDB version: {simdb.__version__}')"

echo "Running tests..."

# Delete and create test reports directory
rm -rf test-reports
mkdir -p test-reports

# Run tests with coverage
python3 -m pytest \
    --cov=simdb \
    --junitxml=test-reports/pytest.xml \
    -v \
    --tb=short

echo "Build and test completed successfully!"
# Generate coverage report
# coverage html -d simdb-coverage-report
# tar czf simdb-coverage-report.tar.gz simdb-coverage-report/

# coverage xml
# cobertura-clover-transform coverage.xml -o clover.xml
