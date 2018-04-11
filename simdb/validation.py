from typing import Dict, List, Tuple

from .database.database import get_local_db
from .database.models import ValidationParameters
from .imas.utils import is_missing


class ValidationError(Exception):
    pass


class TestParameters:
    mandatory: bool
    range: Tuple[float, float]
    mean: Tuple[float, float]
    median: Tuple[float, float]
    stdev: Tuple[float, float]
    mandatory_tests: List[str]

    def __init__(self, mandatory: bool, range: Tuple[float, float], mean: Tuple[float, float],
                 median: Tuple[float, float], stdev: Tuple[float, float], mandatory_tests: List[str]):
        self.mandatory = mandatory
        self.range = range
        self.mean = mean
        self.median = median
        self.stdev = stdev
        self.mandatory_tests = mandatory_tests

    @classmethod
    def from_db_parameters(cls, params: ValidationParameters) -> "TestParameters":
        return TestParameters(
            mandatory=params.mandatory,
            range=(params.range_low, params.range_high),
            mean=(params.mean_low, params.mean_high),
            median=(params.median_low, params.median_high),
            stdev=(params.stdev_low, params.stdev_high),
            mandatory_tests=params.mandatory_tests.split(";")
        )

    def to_db_parameters(self, path: str) -> ValidationParameters:
        return ValidationParameters(
            path=path,
            mandatory=self.mandatory,
            range_low=self.range[0],
            range_high=self.range[1],
            mean_low=self.mean[0],
            mean_high=self.mean[1],
            median_low=self.median[0],
            median_high=self.median[1],
            stdev_low=self.stdev[0],
            stdev_high=self.stdev[1],
            mandatory_tests=";".join(self.mandatory_tests),
        )


def get_metadata(meta: Dict, name: str) -> List[str]:
    val = meta[name]
    if type(val) == list:
        return val
    else:
        return [val]


def verify_metadata(summary_ids: dict, meta: dict) -> None:
    # Match DC element with an IDS entity
    #
    # title
    # creator               dataset_description.ids_properties.provider, dataset_description.data_entry.user
    # subject               CV{?, ?, ?}
    # description           not missing [dataset_description.ids_properties.comment,
    #                       dataset_description.simulation.comment_before, dataset_description.simulation.comment_after,
    #                       dataset_description.simulation.workflow]
    # publisher             not missing
    # contributer
    # date                  dataset_description.creation_date
    # type                  dataset_description.data_entry.pulse_type    CV{pulse, simulation, ...}
    # format                CV{mdsplus, hdf5, ...}
    # identifier            uuid
    # source                uuid, dataset_description.ids_properties.source
    # language              'en'
    # relation              uuid
    # coverage              CV{{spatial},{temporal}}
    #   spatial             CV{core, edge, ....}
    #   temporal            CV{current ramp-up, current flat-top, ....}
    # rights                not missing
    # audience              CV{?, ?, ?}
    # provenance
    # RightsHolder          not missing
    # InstructionalMethod   CV{?, ?, ?}
    # AccrualMethod         dataset_description.imas_version, dataset_description.dd_version
    # AccrualPeriodicity    CV{?, ?, ?}
    # AccrualPolicy         CV{?, ?, ?}
    #
    # device                dataset_description.data_entry.machine
    # shot                  dataset_description.data_entry.pulse
    # run                   dataset_description.data_entry.run
    # epoch                 dataset_description.simulation.time_begin, dataset_description.simulation.time_end,
    #                       dataset_description.simulation.time_step

    # mandatory DC elements with entries in the DATASET_DESCRIPTION ids

    db = get_local_db()

    creators = get_metadata(meta, 'creator')  # List object
    if creators:
        if not is_missing(summary_ids["provider"]):
            if (summary_ids["provider"] not in creators) and not is_missing(summary_ids["user"]):
                if summary_ids["user"] not in creators:
                    raise ValidationError("dataset_description.ids_properties.provider"
                                          " or dataset_description.data_entry.user inconsistent with metadata")
        else:
            raise ValidationError("dataset_description.ids_properties.provider not found in summary IDS")
    else:
        raise ValidationError("no creator provided in metadata")

    subjects = get_metadata(meta, "subject")  # List object
    if subjects:
        cv = db.get_controlled_vocab("subject")
        if cv:
            for subject in subjects:
                if subject not in cv:
                    raise ValidationError("metadata subject inconsistent with Controlled Vocabulary:"
                                          " illegal subject %s" % subject)
    else:
        raise ValidationError("no subject provided in metadata")

    description = get_metadata(meta, 'description')
    if not description:
        raise ValidationError("do description provided in metadata")

    publisher = get_metadata(meta, 'publisher')
    if not publisher:
        raise ValidationError("no publisher provided in metadata")

    date = get_metadata(meta, 'date')
    if len(date) == 1:
        if date[0] != imas_meta["creation_date"]:
            raise ValidationError("dataset_description.ids_properties.creation_date inconsistent with metadata")
    else:
        raise ValidationError("not date provided in metadata")
