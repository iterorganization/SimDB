"""The optional ``REMOTE`` argument of ``simdb simulation`` sub-commands.

``simulation push``, ``pull``, ``data`` and ``validate`` all take an optional
REMOTE before their required arguments. Click cannot express "optional first
argument", so :class:`OptionalRemoteCommand` fills in an empty REMOTE when the
command line does not provide a value for every argument.

Counting raw command line entries instead is what made ``push SIM_ID --replaces
=x`` fail with "Missing argument 'SIM_ID'": the option was counted as an
argument, so no empty REMOTE was inserted.
"""

from unittest import mock

import pytest
from cli_helpers import make_simulation

SUBCOMMANDS = [
    ("push", ()),
    ("validate", ()),
    ("pull", ("directory",)),
    ("data", ("core_profiles/time",)),
]
"""Each sub-command and the arguments that follow its SIM_ID."""


@pytest.fixture
def remote_api():
    with mock.patch("simdb.cli.commands.simulation.RemoteAPI") as remote_api_cls:
        remote_api_cls.return_value.get_validation_schemas.return_value = []
        yield remote_api_cls


@pytest.fixture(autouse=True)
def a_simulation_exists(local_db):
    local_db.get_simulation.return_value = make_simulation("sim")
    local_db.get_simulation.side_effect = None
    return local_db


@pytest.mark.parametrize(("subcommand", "trailing"), SUBCOMMANDS)
@pytest.mark.parametrize(
    "options", [("--username", "bob"), ()], ids=["username", "no-options"]
)
@pytest.mark.parametrize(
    "options_first", [True, False], ids=["options-first", "options-last"]
)
@pytest.mark.parametrize(
    "remote", [("test",), ()], ids=["named-remote", "default-remote"]
)
def test_the_remote_may_be_omitted(
    invoke, remote_api, remote, options_first, options, subcommand, trailing
):
    """REMOTE may be left out, wherever the options appear on the command line."""
    arguments = (*remote, "sim", *trailing)
    argv = (*options, *arguments) if options_first else (*arguments, *options)

    result = invoke("simulation", subcommand, *argv)

    assert remote_api.called, result.output
    used_remote, used_username = remote_api.call_args.args[:2]
    assert used_remote == (remote[0] if remote else "")
    assert used_username == ("bob" if options else None)


@pytest.mark.parametrize(
    ("subcommand", "arguments", "option"),
    [
        ("push", ["sim"], "--replaces=older"),
        ("push", ["sim"], "--add-watcher"),
        ("data", ["sim", "core_profiles/time"], "--dd-version=4.1.1"),
    ],
)
def test_a_command_specific_option_does_not_consume_the_remote(
    invoke, remote_api, subcommand, arguments, option
):
    """Options that are not shared by every sub-command must count the same way."""
    result = invoke("simulation", subcommand, *arguments, option)

    assert "Missing argument" not in result.output
    assert remote_api.call_args.args[0] == ""


@pytest.mark.parametrize(
    ("subcommand", "trailing"),
    [(subcommand, trailing) for subcommand, trailing in SUBCOMMANDS if trailing],
)
def test_a_genuinely_missing_argument_is_still_reported(
    invoke, remote_api, subcommand, trailing
):
    """Filling in the REMOTE must not paper over an argument the user forgot."""
    result = invoke("simulation", subcommand, "sim", *trailing[:-1])

    assert result.exit_code == 2
    assert "Missing argument" in result.output
    assert not remote_api.called


@pytest.mark.parametrize("subcommand", [subcommand for subcommand, _ in SUBCOMMANDS])
def test_a_command_with_no_arguments_at_all_is_reported(invoke, remote_api, subcommand):
    result = invoke("simulation", subcommand)

    assert result.exit_code == 2
    assert "Missing argument" in result.output
    assert not remote_api.called
