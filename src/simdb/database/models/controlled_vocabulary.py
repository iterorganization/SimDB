import uuid
from typing import List, Dict

from sqlalchemy import Column, types as sql_types, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from ._base import Base
from .types import UUID
from ...docstrings import inherit_docstrings


@inherit_docstrings
class ControlledVocabulary(Base):
    """
    Class to represent controlled vocabularies in the database ORM.
    """
    __tablename__ = "controlled_vocabulary"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    name = Column(sql_types.String(250), nullable=False, unique=True)
    words: List["ControlledVocabularyWord"] = relationship("ControlledVocabularyWord")

    def __init__(self, name: str, words: List[str]) -> None:
        self.uuid = uuid.uuid1()
        self.name = name
        self.add_words(words)

    def add_words(self, words: List[str]):
        for word in words:
            self.words.append(ControlledVocabularyWord(word))

    @classmethod
    def from_data(cls, data: Dict) -> "ControlledVocabulary":
        vocab = ControlledVocabulary(data["name"], data["words"])
        vocab.uuid = data["uuid"]
        return vocab

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            name=self.name,
        )
        if recurse:
            data["words"] = [w.data(recurse=True) for w in self.words]
        return data


@inherit_docstrings
class ControlledVocabularyWord(Base):
    """
    Class to represent controlled vocabulary word in the database ORM.
    """
    __tablename__ = "controlled_vocabulary_word"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    vocabulary_id = Column(sql_types.Integer, ForeignKey(ControlledVocabulary.id))
    value = Column(sql_types.Text, nullable=False)
    __table_args__ = (
        UniqueConstraint('vocabulary_id', 'value', name='_vocabulary_word'),
    )

    def __init__(self, value: str) -> None:
        self.uuid = uuid.uuid1()
        self.value = value

    @classmethod
    def from_data(cls, data: Dict) -> "ControlledVocabularyWord":
        word = ControlledVocabularyWord(data["value"])
        word.uuid = data["uuid"]
        return word

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            value=self.value,
        )
        return data