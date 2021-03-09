import uuid
from typing import Dict

from sqlalchemy import Column, types as sql_types, UniqueConstraint

from ._base import Base
from .types import UUID
from ...docstrings import inherit_docstrings


@inherit_docstrings
class ValidationParameters(Base):
    __tablename__ = "validation_parameters"
    id = Column(sql_types.Integer, primary_key=True)
    uuid = Column(UUID, nullable=False)
    device = Column(sql_types.Text, nullable=False)
    scenario = Column(sql_types.Text, nullable=False)
    path = Column(sql_types.Text, nullable=False)
    mandatory = Column(sql_types.Boolean, nullable=False)
    range_low = Column(sql_types.Float, nullable=False)
    range_high = Column(sql_types.Float, nullable=False)
    mean_low = Column(sql_types.Float, nullable=False)
    mean_high = Column(sql_types.Float, nullable=False)
    median_low = Column(sql_types.Float, nullable=False)
    median_high = Column(sql_types.Float, nullable=False)
    stdev_low = Column(sql_types.Float, nullable=False)
    stdev_high = Column(sql_types.Float, nullable=False)
    mandatory_tests = Column(sql_types.Text, nullable=False)

    __table_args__ = (
        UniqueConstraint('device', 'scenario', 'path', name='_validation_parameters_identifier'),
    )

    def __init__(self, device: str, scenario: str, path: str, mandatory: bool, range_low: float, range_high: float,
                 mean_low: float, mean_high: float, median_low: float, median_high: float,
                 stdev_low: float, stdev_high: float, mandatory_tests: str) -> None:
        self.uuid = uuid.uuid1()
        self.device = device
        self.scenario = scenario
        self.path = path
        self.mandatory = mandatory
        self.range_low = range_low
        self.range_high = range_high
        self.mean_low = mean_low
        self.mean_high = mean_high
        self.median_low = median_low
        self.median_high = median_high
        self.stdev_low = stdev_low
        self.stdev_high = stdev_high
        self.mandatory_tests = mandatory_tests

    @classmethod
    def from_data(cls, data: Dict) -> "ValidationParameters":
        params = ValidationParameters(data["device"], data["scenario"], data["path"], data["mandatory"],
                                      data["range_low"], data["range_high"], data["mean_low"], data["mean_high"],
                                      data["median_low"], data["median_high"], data["stdev_low"], data["stdev_high"],
                                      data["mandatory_tests"])
        params.uuid = data["uuid"]
        return params

    def data(self, recurse: bool = False) -> Dict:
        data = dict(
            uuid=self.uuid.hex,
            device=self.device,
            scenario=self.scenario,
            path=self.path,
            mandatory=self.mandatory,
            range_low=self.range_low,
            range_high=self.range_high,
            mean_low=self.mean_low,
            mean_high=self.mean_high,
            median_low=self.median_low,
            median_high=self.median_high,
            stdev_low=self.stdev_low,
            stdev_high=self.stdev_high,
            mandatory_tests=self.mandatory_tests,
        )
        return data
