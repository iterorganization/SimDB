import smtplib
import socket
from email.message import EmailMessage
from typing import List

from email_validator import validate_email

from simdb.config import Config


class EmailServer:
    _server: str
    _port: int
    _user: str
    _password: str
    _instance: str

    def __init__(self, config: Config):
        self._server = config.get_string_option("email.server")
        self._port = int(config.get_option("email.port"))
        self._user = config.get_string_option("email.user")
        self._password = config.get_string_option("email.password")
        self._instance = config.get_string_option("server.name", default=None) or (
            socket.getfqdn()
        )

    def send_message(self, subject: str, body: str, to_addresses: List[str]):
        """Email the recipients, each hidden from the others in Bcc."""
        message = EmailMessage()
        message["From"] = self._user
        message["To"] = self._user
        message["Bcc"] = ", ".join(validate_email(i).email for i in to_addresses)
        message["Subject"] = f"[SimDB {self._instance}] {subject}"
        message.set_content(f"{body}\n\nSent by the SimDB server {self._instance}.\n")

        server = smtplib.SMTP(self._server, self._port)
        server.starttls()
        server.login(self._user, self._password)
        server.send_message(message)
        server.close()
