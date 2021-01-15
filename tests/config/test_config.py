from unittest import mock
from simdb.config.config import Config
from io import StringIO
import simdb


def test_create_config():
    Config()


@mock.patch('appdirs.site_config_dir')
@mock.patch('appdirs.user_config_dir')
def test_load_config(user_config_dir, site_config_dir):
    config = Config()
    config.load()
    user_config_dir.assert_called_once_with('simdb')
    site_config_dir.assert_called_once_with('simdb')
    assert config.list_options() == []
    assert config.api_version == simdb.__version__


@mock.patch('appdirs.site_config_dir')
@mock.patch('appdirs.user_config_dir')
def test_load_config_from_specified_file(user_config_dir, site_config_dir):
    config = Config()
    stream = StringIO()
    stream.write("""
    [db]
    type = sqlite
    file = /tmp/simdb.db
    """)
    stream.seek(0)
    config.load(file=stream)
    user_config_dir.assert_called_once_with('simdb')
    site_config_dir.assert_called_once_with('simdb')
    assert config.list_options() == [
        'db-type: sqlite',
        'db-file: /tmp/simdb.db',
    ]
    assert config.api_version == simdb.__version__
