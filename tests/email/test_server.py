from unittest import mock

import pytest

from simdb.config import Config
from simdb.email.server import EmailServer

SENDER = "simdb@example.org"
WATCHERS = ["alice@example.org", "bob@example.org"]


@pytest.fixture
def config():
    config = Config()
    config.set_option("email.server", "smtp.example.org")
    config.set_option("email.port", "587")
    config.set_option("email.user", SENDER)
    config.set_option("email.password", "secret")
    return config


def _send(config, subject="Simulation 100001/1", body="Status changed."):
    validate = mock.patch(
        "simdb.email.server.validate_email",
        side_effect=lambda address: mock.Mock(email=address),
    )
    with mock.patch("simdb.email.server.smtplib.SMTP") as smtp, validate:
        EmailServer(config).send_message(subject, body, WATCHERS)
    (message,), _ = smtp.return_value.send_message.call_args
    return message


def test_watchers_are_not_shown_to_each_other(config):
    message = _send(config)

    assert message["To"] == SENDER
    assert all(address not in str(message["To"]) for address in WATCHERS)
    assert message["Bcc"] == ", ".join(WATCHERS)


def test_message_names_the_configured_instance(config):
    config.set_option("server.name", "ITER production")

    message = _send(config)

    assert message["Subject"] == "[SimDB ITER production] Simulation 100001/1"
    assert "Sent by the SimDB server ITER production." in message.get_content()


def test_instance_name_defaults_to_hostname(config):
    with mock.patch("simdb.email.server.socket.getfqdn", return_value="simdb.host"):
        message = _send(config)

    assert message["Subject"] == "[SimDB simdb.host] Simulation 100001/1"
    assert "Sent by the SimDB server simdb.host." in message.get_content()
