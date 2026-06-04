import tempfile
import uuid
from datetime import datetime, timezone

import pytest

from simdb.database import Database
from simdb.database.models import Base, Simulation
from simdb.query import QueryType


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_file = f.name
    database = Database(Database.DBMS.SQLITE, file=db_file)
    Base.metadata.create_all(database.engine)
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
