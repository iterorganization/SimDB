import tempfile
import uuid
from datetime import date, datetime, timezone

import pytest

from simdb.database import Database
from simdb.database.models import Base, Simulation
from simdb.query import QueryType


@pytest.fixture
def db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_file = f.name
    database = Database(Database.DBMS.SQLITE, file=db_file)
    Base.metadata.create_all(database.engine)

    original_query_all = database.session.query(Simulation).__class__.all
    unordered_query_calls = {"value": 0}

    def unstable_order(self):
        # PostgreSQL does not guarantee row order without ORDER BY; see
        # https://www.postgresql.org/docs/current/queries-order.html.
        # Unless "_order_by_clauses" is set, mimic the unstable ordering.
        if getattr(self, "_order_by_clauses", ()):
            return list(original_query_all(self))

        rows = list(original_query_all(self))
        if not rows:
            return rows

        # Simple rotation of rows, at every call to query.all()
        unordered_query_calls["value"] += 1
        rotation = (unordered_query_calls["value"] - 1) % len(rows)
        rows = rows[rotation:] + rows[:rotation]
        return rows

    monkeypatch.setattr(
        database.session.query(Simulation).__class__, "all", unstable_order
    )

    yield database
    database.close()


def create_simulation(alias=None, metadata=None):
    sim = Simulation(None)
    sim.uuid = uuid.uuid1()
    sim.alias = alias or uuid.uuid4().hex
    sim.datetime = datetime.now(timezone.utc)
    if metadata:
        for key, value in metadata.items():
            sim.set_meta(key, value)
    return sim


class TestQueryMeta:
    def test_query_meta_empty_database(self, db):
        results = db.query_meta([("status", "passed", QueryType.EQ)])
        assert results == []

    def test_query_meta_single_constraint_eq(self, db):
        sim1 = create_simulation(metadata={"status": "passed"})
        sim2 = create_simulation(metadata={"status": "failed"})
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.session.commit()

        results = db.query_meta([("status", "passed", QueryType.EQ)])
        assert len(results) == 1
        assert results[0].find_meta("status") == ["passed"]

    def test_query_meta_single_constraint_ne(self, db):
        sim1 = create_simulation(metadata={"status": "passed"})
        sim2 = create_simulation(metadata={"status": "failed"})
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.session.commit()

        results = db.query_meta([("status", "passed", QueryType.NE)])
        assert len(results) == 1
        assert results[0].find_meta("status") == ["failed"]

    def test_query_meta_multiple_constraints(self, db):
        sim1 = create_simulation(metadata={"status": "passed", "type": "A"})
        sim2 = create_simulation(metadata={"status": "failed", "type": "B"})
        sim3 = create_simulation(metadata={"status": "passed", "type": "B"})
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        results = db.query_meta(
            [("status", "passed", QueryType.EQ), ("type", "B", QueryType.EQ)]
        )
        assert len(results) == 1
        assert results[0].find_meta("type") == ["B"]

    def test_query_meta_no_match(self, db):
        sim = create_simulation(metadata={"status": "passed"})
        db.insert_simulation(sim)
        db.session.commit()

        results = db.query_meta([("status", "failed", QueryType.EQ)])
        assert results == []

    def test_query_meta_by_alias(self, db):
        sim1 = create_simulation(alias="test_alias_1", metadata={"status": "passed"})
        sim2 = create_simulation(alias="test_alias_2", metadata={"status": "failed"})
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.session.commit()

        results = db.query_meta([("alias", "test_alias_1", QueryType.EQ)])
        assert len(results) == 1
        assert results[0].alias == "test_alias_1"

    def test_query_meta_in_comparator(self, db):
        sim1 = create_simulation(metadata={"description": "test simulation A"})
        sim2 = create_simulation(metadata={"description": "another test"})
        sim3 = create_simulation(metadata={"description": "other"})
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        results = db.query_meta([("description", "test", QueryType.IN)])
        assert len(results) == 2

    def test_query_meta_ni_comparator(self, db):
        sim1 = create_simulation(metadata={"description": "test simulation A"})
        sim2 = create_simulation(metadata={"description": "another test"})
        sim3 = create_simulation(metadata={"description": "other"})
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        results = db.query_meta([("description", "test", QueryType.NI)])
        assert len(results) == 1
        assert results[0].find_meta("description") == ["other"]

    def test_query_meta_exist_comparator(self, db):
        sim1 = create_simulation(metadata={"status": "passed"})
        sim2 = create_simulation(metadata={})
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.session.commit()

        results = db.query_meta([("status", "true", QueryType.EXIST)])
        assert len(results) == 1
        assert results[0].find_meta("status") == ["passed"]

    def test_query_meta_agt_comparator(self, db):
        sim1 = create_simulation(
            alias="sim1", metadata={"range": {"min": 1.0, "max": 5.0}}
        )
        sim2 = create_simulation(
            alias="sim2", metadata={"range": {"min": 2.0, "max": 3.0}}
        )
        sim3 = create_simulation(
            alias="sim3", metadata={"range": {"min": 6.0, "max": 10.0}}
        )
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        results = db.query_meta([("range", "4", QueryType.AGT)])
        assert len(results) == 2
        aliases = {r.alias for r in results}
        assert aliases == {"sim1", "sim3"}

    def test_query_meta_age_comparator(self, db):
        sim1 = create_simulation(
            alias="sim1", metadata={"range": {"min": 1.0, "max": 5.0}}
        )
        sim2 = create_simulation(
            alias="sim2", metadata={"range": {"min": 2.0, "max": 3.0}}
        )
        sim3 = create_simulation(
            alias="sim3", metadata={"range": {"min": 6.0, "max": 10.0}}
        )
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        results = db.query_meta([("range", "5", QueryType.AGE)])
        assert len(results) == 2

    def test_query_meta_alt_comparator(self, db):
        sim1 = create_simulation(
            alias="sim1", metadata={"range": {"min": 1.0, "max": 5.0}}
        )
        sim2 = create_simulation(
            alias="sim2", metadata={"range": {"min": 2.0, "max": 3.0}}
        )
        sim3 = create_simulation(
            alias="sim3", metadata={"range": {"min": 6.0, "max": 10.0}}
        )
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        results = db.query_meta([("range", "4", QueryType.ALT)])
        assert len(results) == 2
        aliases = {r.alias for r in results}
        assert aliases == {"sim1", "sim2"}

    def test_query_meta_ale_comparator(self, db):
        sim1 = create_simulation(
            alias="sim1", metadata={"range": {"min": 1.0, "max": 5.0}}
        )
        sim2 = create_simulation(
            alias="sim2", metadata={"range": {"min": 2.0, "max": 3.0}}
        )
        sim3 = create_simulation(
            alias="sim3", metadata={"range": {"min": 6.0, "max": 10.0}}
        )
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        results = db.query_meta([("range", "3", QueryType.ALE)])
        assert len(results) == 2

    def test_query_meta_range_combined_constraints(self, db):
        sim1 = create_simulation(
            alias="sim1", metadata={"range": {"min": 1.0, "max": 5.0}}
        )
        sim2 = create_simulation(
            alias="sim2", metadata={"range": {"min": 2.0, "max": 3.0}}
        )
        sim3 = create_simulation(
            alias="sim3", metadata={"range": {"min": 4.0, "max": 7.0}}
        )
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        results = db.query_meta(
            [
                ("range", "3", QueryType.AGT),
                ("range", "5", QueryType.ALT),
            ]
        )
        assert len(results) == 2
        aliases = {r.alias for r in results}
        assert aliases == {"sim1", "sim3"}


class TestRangeWithScalarComparators:
    """eq/ne/in/ni/gt/ge/lt/le on metadata stored as a {min, max} range.

    Numeric arrays are stored as ranges (see the 28bee3aa2429 migration), so a
    query such as ``global_quantities.ip.value=gt:...`` has to compare against
    the range instead of treating it as a non-numeric value.
    """

    @pytest.fixture
    def sims(self, db):
        for alias, value in [
            ("low", {"min": 1.0, "max": 3.0}),
            ("mid", {"min": 4.0, "max": 6.0}),
            ("high", {"min": 7.0, "max": 9.0}),
            ("scalar", 5.0),
            ("text", "five"),
            ("other_object", {"name": "x"}),
        ]:
            db.insert_simulation(create_simulation(alias=alias, metadata={"v": value}))
        db.insert_simulation(create_simulation(alias="missing", metadata={"w": 1}))
        db.session.commit()

    def aliases(self, db, value, query_type):
        return {r.alias for r in db.query_meta([("v", value, query_type)])}

    @pytest.mark.parametrize(
        "value, query_type, expected",
        [
            # The whole range must satisfy gt/ge/lt/le.
            ("3.5", QueryType.GT, {"mid", "high", "scalar"}),
            ("4", QueryType.GT, {"high", "scalar"}),
            ("4", QueryType.GE, {"mid", "high", "scalar"}),
            ("6.5", QueryType.LT, {"low", "mid", "scalar"}),
            ("6", QueryType.LT, {"low", "scalar"}),
            ("6", QueryType.LE, {"low", "mid", "scalar"}),
            # eq matches ranges containing the value, including the bounds.
            ("5", QueryType.EQ, {"mid"}),
            ("4", QueryType.EQ, {"mid"}),
            ("9", QueryType.EQ, {"high"}),
            ("3.5", QueryType.EQ, set()),
            # ne matches ranges not containing it, and differing other values.
            ("5", QueryType.NE, {"low", "high", "scalar", "text", "other_object"}),
            # in/ni behave like eq/ne on a range.
            # A scalar keeps the substring match: "5.0" contains "5".
            ("5", QueryType.IN, {"mid", "scalar"}),
            ("3.5", QueryType.IN, set()),
            ("5", QueryType.NI, {"low", "high", "text", "other_object"}),
            # Non-numeric values are still compared as strings.
            ("fiv", QueryType.IN, {"text"}),
            ("five", QueryType.EQ, {"text"}),
            ("five", QueryType.NE, {"low", "mid", "high", "scalar", "other_object"}),
        ],
    )
    def test_range_comparison(self, db, sims, value, query_type, expected):
        assert self.aliases(db, value, query_type) == expected

    def test_any_comparators_unchanged(self, db, sims):
        assert self.aliases(db, "8", QueryType.AGT) == {"high"}
        assert self.aliases(db, "2", QueryType.ALT) == {"low"}


class TestListSimulationData:
    def test_list_simulation_data_empty_database(self, db):
        count, results = db.list_simulation_data([])
        assert count == 0
        assert results == []

    def test_list_simulation_data_returns_correct_format(self, db):
        sim = create_simulation(alias="test_sim", metadata={"status": "passed"})
        db.insert_simulation(sim)
        db.session.commit()

        count, results = db.list_simulation_data(["status"])
        assert count == 1
        assert len(results) == 1
        assert results[0]["alias"] == "test_sim"
        assert results[0]["metadata"] == [{"element": "status", "value": "passed"}]

    def test_list_simulation_data_with_limit(self, db):
        for i in range(5):
            sim = create_simulation(metadata={"index": str(i)})
            db.insert_simulation(sim)
        db.session.commit()

        count, results = db.list_simulation_data(["index"], limit=2)
        assert count == 5
        assert len(results) == 2

    def test_list_simulation_data_with_page(self, db):
        for i in range(5):
            sim = create_simulation(metadata={"index": str(i)})
            db.insert_simulation(sim)
        db.session.commit()

        count, results = db.list_simulation_data(["index"], limit=2, page=2)
        assert count == 5
        assert len(results) == 2

    def test_list_simulation_data_with_sort_by_metadata(self, db):
        sim1 = create_simulation(metadata={"value": "3"})
        sim2 = create_simulation(metadata={"value": "1"})
        sim3 = create_simulation(metadata={"value": "2"})
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        count, results = db.list_simulation_data(
            ["value"], sort_by="value", sort_asc=True
        )
        assert count == 3
        values = [r["metadata"][0]["value"] for r in results]
        assert values == ["1", "2", "3"]

    def test_list_simulation_data_with_sort_by_alias(self, db):
        sim1 = create_simulation(alias="c_sim")
        sim2 = create_simulation(alias="a_sim")
        sim3 = create_simulation(alias="b_sim")
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.session.commit()

        count, results = db.list_simulation_data([], sort_by="alias", sort_asc=True)
        assert count == 3
        aliases = [r["alias"] for r in results]
        assert aliases == ["a_sim", "b_sim", "c_sim"]

    def test_db_fixture_returns_unstable_order_without_sort(self, db):
        sim1 = create_simulation(alias="sim1")
        sim2 = create_simulation(alias="sim2")
        sim3 = create_simulation(alias="sim3")
        sim4 = create_simulation(alias="sim4")

        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.insert_simulation(sim4)
        db.session.commit()

        query = db.session.query(Simulation)
        page1_count = query.count()
        page1 = query.all()[:2]

        query = db.session.query(Simulation)
        page2_count = query.count()
        page2 = query.all()[2:4]

        assert page1_count == page2_count == 4
        assert len(page1) == len(page2) == 2

        page1_aliases = {row.alias for row in page1}
        page2_aliases = {row.alias for row in page2}

        # Without a stable sort key, page 1 and page 2 can overlap.
        assert len(page1_aliases & page2_aliases) == 1
        assert len(page1_aliases | page2_aliases) == 3

    def test_list_simulation_data_is_stable_without_explicit_sort(self, db):
        sim1 = create_simulation()
        sim2 = create_simulation()
        sim3 = create_simulation()
        sim4 = create_simulation()

        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.insert_simulation(sim3)
        db.insert_simulation(sim4)
        db.session.commit()

        first_count, first_page = db.list_simulation_data(limit=2, page=1)
        second_count, second_page = db.list_simulation_data(limit=2, page=1)

        assert first_count == second_count == 4
        assert first_page == second_page


class TestQueryMetaData:
    def test_query_meta_data_empty_constraints(self, db):
        sim = create_simulation(alias="test_sim", metadata={"status": "passed"})
        db.insert_simulation(sim)
        db.session.commit()

        count, results = db.query_meta_data([], ["status"])
        assert count == 1, results
        assert results[0]["metadata"] == [{"element": "status", "value": "passed"}]

    def test_query_meta_data_with_constraint(self, db):
        sim1 = create_simulation(metadata={"status": "passed", "type": "A"})
        sim2 = create_simulation(metadata={"status": "failed", "type": "B"})
        db.insert_simulation(sim1)
        db.insert_simulation(sim2)
        db.session.commit()

        count, results = db.query_meta_data(
            [("status", "passed", QueryType.EQ)], ["type"]
        )
        assert count == 1
        assert len(results) == 1
        assert results[0]["metadata"] == [{"element": "type", "value": "A"}]


class TestDatetimeMetadata:
    # Regression for #131: unquoted manifest timestamps are parsed by YAML into
    # date/datetime objects, which failed ingest and push with
    # "Object of type datetime is not JSON serializable".
    def test_datetime_metadata_is_stored_as_isoformat_strings(self, db):
        sim = create_simulation(
            metadata={
                "run_date": date(2026, 9, 16),
                "run_start": datetime(2026, 9, 16, 15, 55, 48),
            }
        )

        db.insert_simulation(sim)

        loaded = db.get_simulation(sim.uuid.hex)
        assert loaded.find_meta("run_date") == ["2026-09-16"]
        assert loaded.find_meta("run_start") == ["2026-09-16T15:55:48"]
        # The push payload is built from the stored simulation.
        assert "2026-09-16T15:55:48" in loaded.to_model(recurse=True).model_dump_json()
