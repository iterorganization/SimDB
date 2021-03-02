from typing import Dict

from email_validator import validate_email
from sqlalchemy import Column, types as sql_types
from sqlalchemy.orm import validates

from . import Base
from .types import ChoiceType
from ...docstrings import inherit_docstrings


@inherit_docstrings
class Watcher(Base):
    """
    Class to represent people watching simulations for updates.
    """
    NOTIFICATION_CHOICES = {
        'V': 'validation',
        'R': 'revision',
        'O': 'obsolescence',
        'A': 'all',
    }

    __tablename__ = "watchers"
    id = Column(sql_types.Integer, primary_key=True)
    username = Column(sql_types.String(250))
    email = Column(sql_types.String(1000))
    notification = ChoiceType(choices=NOTIFICATION_CHOICES, length=1)

    @validates('email')
    def validate_email(self, key, address):
        validate_email(address)
        return address

    def __init__(self, username, email, notification):
        self.username = username
        self.email = email
        self.notification = notification

    @classmethod
    def from_data(cls, data: Dict) -> "Watcher":
        watcher = Watcher(data["username"], data["email"])
        return watcher

    def data(self, recurse: bool=False) -> Dict[str, str]:
        data = dict(
            username=self.username,
            email=self.email,
        )
        return data
