from pathlib import Path


def config_test_file() -> Path:
    config = """\
[remote "test"]
url = http://0.0.0.0:5000/
default = True
"""
    config_file = Path(__file__).parent / 'test.cfg'
    config_file.write_text(config)
    return config_file


def create_manifest() -> Path:
    manifest = """\
version: 1
alias: simulation-alias

# Data and configuration files
inputs:
  - uri: simdb://simdb.iter.org/123e4567-e89b-12d3-a456-426655440000
  - uri: file:///home/user/path/to/a/file1
  - uri: imas:///user?shot=10000&run=0
  - uri: imas+uda:///TOKAMAK?shot=10000&run=0&server=uda.server.org:56565

# Data and log files.
outputs:
  - uri: file:///home/user/path/to/a/file2
  - uri: imas:///user?shot=10000&run=1

metadata:
- values:
    workflow:
      name: Workflow Name
      git: ssh://git@git.iter.org/wf/workflow.git
      branch: master
      commit: 079e84d5ae8a0eec6dcf3819c98f3c05f48e952f
      codes:
        - Code 1:
            git: ssh://git@git.iter.org/eq/code.git
            commit: 079e84d5ae8a0eec6dcf3819c98f3c05f48e952f
"""
    manifest_file = Path(__file__).parent / 'manifest.yaml'
    manifest_file.write_text(manifest)
    return manifest_file


def get_file_path(file_name) -> Path:
    return Path(__file__).parent / file_name
