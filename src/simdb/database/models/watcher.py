from typing import Dict

from email_validator import validate_email
from sqlalchemy import Column, types as sql_types
from sqlalchemy.orm import validates

from .base import Base
from .types import ChoiceType
from ...docstrings import inherit_docstrings


@inherit_docstrings
class Watcher(Base):
    """
    Class to represent people watching simulations for updates.
    """
    NOTIFICATION_CHOICES = {
        'validation':   'V',
        'revision':     'R',
        'obsolescence': 'O',
        'all':          'A',
    }

    __tablename__ = "watchers"
    id = Column(sql_types.Integer, primary_key=True)
    username = Column(sql_types.String(250))
    email = Column(sql_types.String(1000))
    notification = Column(ChoiceType(choices=NOTIFICATION_CHOICES, length=1))

    @validates('email')
    def validate_email(self, key, address):
        validate_email(address)
        return address

    def __init__(self, username: str, email: str, notification: str):
        self.username = username
        self.email = email
        self.notification = notification.lower()

    @classmethod
    def from_data(cls, data: Dict) -> "Watcher":
        watcher = Watcher(data["username"], data["email"], data["notification"])
        return watcher

    def data(self, recurse: bool=False) -> Dict[str, str]:
        data = dict(
            username=self.username,
            email=self.email,
            notification=str(self.notification),
        )
        return data
