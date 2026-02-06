import smtplib
from typing import List

from email_validator import validate_email

from simdb.config import Config


class EmailServer:
    _server: str
    _port: int
    _user: str
    _password: str

    def __init__(self, config: Config):
        self._server = config.get_string_option("email.server")
        self._port = int(config.get_option("email.port"))
        self._user = config.get_string_option("email.user")
        self._password = config.get_string_option("email.password")

    def send_message(self, subject: str, body: str, to_addresses: List[str]):
        server = smtplib.SMTP(self._server, self._port)
        server.starttls()
        server.login(self._user, self._password)
        sent_to = [validate_email(i).email for i in to_addresses]
        sent_to_list = ",".join(sent_to)

        email_text = f"""\
From: {self._user}
To: {sent_to_list}
Subject: {subject}

{body}
"""

        server.sendmail(self._user, sent_to, email_text)
        server.close()
