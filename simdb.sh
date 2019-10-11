#!/bin/bash
# PYTHON_ARGCOMPLETE_OK

#dgm module purge
#dgm module load anaconda3
export PATH=$HOME/anaconda3/bin:$PATH

export SIMDB_USER_CONFIG_PATH=$HOME/.simdb/config.cfg
#export SIMDB_SITE_CONFIG_PATH=$HOME/.simdb/site_config.cfg

source activate simdb

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"

export PYTHONPATH=$DIR:$PYTHONPATH
python3 -m simdb.cli "$@"
