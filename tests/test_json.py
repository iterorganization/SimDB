import datetime

import pytest

from simdb.json import CustomEncoder, json


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            datetime.datetime(2026, 9, 16, 15, 55, 48, 489333),
            "2026-09-16T15:55:48.489333",
        ),
        (
            datetime.datetime(2026, 9, 16, 15, 55, 48, tzinfo=datetime.timezone.utc),
            "2026-09-16T15:55:48+00:00",
        ),
        (datetime.date(2026, 9, 16), "2026-09-16"),
        (datetime.time(15, 55, 48), "15:55:48"),
    ],
)
def test_custom_encoder_encodes_datetimes_as_isoformat(value, expected):
    assert json.loads(json.dumps({"when": value}, cls=CustomEncoder)) == {
        "when": expected
    }
