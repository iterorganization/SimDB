import uuid
from typing import Optional, Dict

import uri as urilib
from sqlalchemy import types as sql_types


class UUID(sql_types.TypeDecorator):
    """
    Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as stringified hex values.
    """
    impl = sql_types.CHAR

    @property
    def python_type(self):
        return uuid.UUID

    def load_dialect_impl(self, dialect):
        from sqlalchemy.dialects import postgresql

        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID())
        else:
            return dialect.type_descriptor(sql_types.CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                try:
                    return uuid.UUID(value).hex
                except ValueError:
                    return value
            else:
                return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value

    def process_literal_param(self, value, dialect):
        return self.process_result_value(value, dialect)


class URI(sql_types.TypeDecorator):
    """
    UUID type for reading/writing to the ORM.
    """
    impl = sql_types.CHAR

    @property
    def python_type(self):
        return urilib.URI

    def process_bind_param(self, value: Optional[urilib.URI], dialect) -> Optional[str]:
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value: Optional[str], dialect) -> Optional[urilib.URI]:
        if value is None:
            return value
        return urilib.URI(value)

    def process_literal_param(self, value, dialect) -> Optional[urilib.URI]:
        return self.process_result_value(value, dialect)


class ChoiceType(sql_types.TypeDecorator):

    impl = sql_types.CHAR

    @property
    def python_type(self):
        return str

    def __init__(self, choices: Dict[str, str], **kw):
        self.choices_inverse = dict(choices)
        self.choices = {v: k for k, v in self.choices_inverse.items()}
        if len(self.choices) != len(self.choices_inverse):
            raise TypeError('Values in choices dict must be unique')
        super().__init__(**kw)

    def process_bind_param(self, value, dialect):
        return self.choices_inverse[value]

    def process_result_value(self, value, dialect):
        return self.choices[value]

    def process_literal_param(self, value, dialect):
        return self.process_result_value(value, dialect)
