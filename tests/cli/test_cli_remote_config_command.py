"""Tests for ``simdb remote config``.

These commands only touch the configuration file, so no remote is involved. The
file they write back to is the throw-away one the ``config_file`` fixture
creates inside ``tmp_path``.
"""

import configparser

import pytest


@pytest.fixture
def saved_config(config_file):
    """Read back what ``Config.save`` wrote.

    ``Config.load`` treats a ``--config-file`` as the user configuration, so
    that is the file ``save`` writes back to.
    """

    def _saved_config() -> configparser.ConfigParser:
        parser = configparser.ConfigParser()
        parser.read(config_file)
        return parser

    return _saved_config


def test_list_shows_the_configured_remotes(invoke):
    result = invoke("remote", "config", "list")

    assert result.exit_code == 0
    assert "test: http://0.0.0.0:5000/ (default)" in result.output


def test_list_shows_the_username_and_firewall_of_a_remote(invoke):
    assert (
        invoke("remote", "config", "set-option", "test", "username", "me").exit_code
        == 0
    )
    assert (
        invoke("remote", "config", "set-option", "test", "firewall", "F5").exit_code
        == 0
    )

    result = invoke("remote", "config", "list")

    assert result.exit_code == 0
    assert "firewall: F5" in result.output
    assert "username: me" in result.output


def test_default_prints_the_default_remote(invoke):
    result = invoke("remote", "config", "default")

    assert result.exit_code == 0
    assert result.output.strip() == "test"


def test_get_default_prints_the_default_remote(invoke):
    result = invoke("remote", "config", "get-default")

    assert result.exit_code == 0
    assert result.output.strip() == "test"


def test_new_adds_a_remote(invoke, saved_config):
    result = invoke("remote", "config", "new", "other", "http://other.test")

    assert result.exit_code == 0
    assert saved_config()['remote "other"']["url"] == "http://other.test"


def test_new_can_record_a_username_and_firewall(invoke, saved_config):
    result = invoke(
        "remote",
        "config",
        "new",
        "other",
        "http://other.test",
        "--username=me",
        "--firewall=F5",
    )

    assert result.exit_code == 0
    section = saved_config()['remote "other"']
    assert section["username"] == "me"
    assert section["firewall"] == "F5"


def test_new_rejects_an_unknown_firewall(invoke):
    result = invoke(
        "remote", "config", "new", "other", "http://other.test", "--firewall=nope"
    )

    assert result.exit_code == 2


def test_new_can_make_the_remote_the_default(invoke, saved_config):
    result = invoke(
        "remote", "config", "new", "other", "http://other.test", "--default"
    )

    assert result.exit_code == 0
    config = saved_config()
    assert config.getboolean('remote "other"', "default") is True
    assert config.getboolean('remote "test"', "default") is False


def test_set_default_switches_the_default_remote(invoke, saved_config):
    assert (
        invoke("remote", "config", "new", "other", "http://other.test").exit_code == 0
    )

    result = invoke("remote", "config", "set-default", "other")

    assert result.exit_code == 0
    assert saved_config().getboolean('remote "other"', "default") is True


def test_delete_removes_a_remote(invoke, saved_config):
    assert (
        invoke("remote", "config", "new", "other", "http://other.test").exit_code == 0
    )

    result = invoke("remote", "config", "delete", "other")

    assert result.exit_code == 0
    assert 'remote "other"' not in saved_config().sections()


def test_set_option_stores_an_arbitrary_option(invoke, saved_config):
    result = invoke("remote", "config", "set-option", "test", "token", "NEWTOKEN")

    assert result.exit_code == 0
    assert saved_config()['remote "test"']["token"] == "NEWTOKEN"


@pytest.mark.parametrize(
    ("subcommand", "arguments"),
    [
        ("new", ["only-a-name"]),
        ("delete", []),
        ("set-default", []),
        ("set-option", ["test", "token"]),
    ],
)
def test_missing_arguments_are_reported(invoke, subcommand, arguments):
    result = invoke("remote", "config", subcommand, *arguments)

    assert result.exit_code == 2
    assert "Missing argument" in result.output
