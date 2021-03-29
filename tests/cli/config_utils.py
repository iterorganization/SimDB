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
