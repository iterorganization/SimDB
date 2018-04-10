from .database.database import get_local_db
from .imas.utils import is_missing


class ValidationError(Exception):
    pass


def verify_metadata(imas_meta: dict, uuid: str) -> None:
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

    creators = db.get_metadata(uuid, 'creator')  # List object
    if creators:
        if not is_missing(imas_meta["provider"]):
            if (imas_meta["provider"] not in creators) and not is_missing(imas_meta["user"]):
                if imas_meta["user"] not in creators:
                    raise ValidationError("dataset_description.ids_properties.provider"
                                          " or dataset_description.data_entry.user inconsistent with metadata")
        else:
            raise ValidationError("dataset_description.ids_properties.provider not found in IDS")
    else:
        raise ValidationError("no creator provided in metadata")

    subjects = db.get_metadata(uuid, "subject")  # List object
    if subjects:
        cv = db.get_controlled_vocab("subject")
        if cv:
            for subject in subjects:
                if subject not in cv:
                    raise ValidationError("metadata subject inconsistent with Controlled Vocabulary:"
                                          " illegal subject %s" % subject)
    else:
        raise ValidationError("no subject provided in metadata")

    description = db.get_metadata(uuid, 'description')
    if not description:
        raise ValidationError("do description provided in metadata")

    publisher = db.get_metadata(uuid, 'publisher')
    if not publisher:
        raise ValidationError("no publisher provided in metadata")

    date = db.get_metadata(uuid, 'date')
    if len(date) == 1:
        if date[0] != imas_meta["creation_date"]:
            raise ValidationError("dataset_description.ids_properties.creation_date inconsistent with metadata")
    else:
        raise ValidationError("not date provided in metadata")
