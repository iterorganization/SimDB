import pytest

from simdb.query import QueryType, parse_query_arg


class TestParseQueryArg:
    def test_parse_simple_value_returns_equal(self):
        value, query_type = parse_query_arg("test_value")
        assert value == "test_value"
        assert query_type == QueryType.EQ

    def test_parse_empty_value_returns_none(self):
        value, query_type = parse_query_arg("")
        assert value == ""
        assert query_type == QueryType.NONE

    def test_parse_eq_comparator(self):
        value, query_type = parse_query_arg("eq:test_value")
        assert value == "test_value"
        assert query_type == QueryType.EQ

    def test_parse_ne_comparator(self):
        value, query_type = parse_query_arg("ne:test_value")
        assert value == "test_value"
        assert query_type == QueryType.NE

    def test_parse_in_comparator(self):
        value, query_type = parse_query_arg("in:test_value")
        assert value == "test_value"
        assert query_type == QueryType.IN

    def test_parse_ni_comparator(self):
        value, query_type = parse_query_arg("ni:test_value")
        assert value == "test_value"
        assert query_type == QueryType.NI

    def test_parse_gt_comparator(self):
        value, query_type = parse_query_arg("gt:10")
        assert value == "10"
        assert query_type == QueryType.GT

    def test_parse_ge_comparator(self):
        value, query_type = parse_query_arg("ge:10")
        assert value == "10"
        assert query_type == QueryType.GE

    def test_parse_lt_comparator(self):
        value, query_type = parse_query_arg("lt:10")
        assert value == "10"
        assert query_type == QueryType.LT

    def test_parse_le_comparator(self):
        value, query_type = parse_query_arg("le:10")
        assert value == "10"
        assert query_type == QueryType.LE

    def test_parse_agt_comparator(self):
        value, query_type = parse_query_arg("agt:10")
        assert value == "10"
        assert query_type == QueryType.AGT

    def test_parse_age_comparator(self):
        value, query_type = parse_query_arg("age:10")
        assert value == "10"
        assert query_type == QueryType.AGE

    def test_parse_alt_comparator(self):
        value, query_type = parse_query_arg("alt:10")
        assert value == "10"
        assert query_type == QueryType.ALT

    def test_parse_ale_comparator(self):
        value, query_type = parse_query_arg("ale:10")
        assert value == "10"
        assert query_type == QueryType.ALE

    def test_parse_exist_comparator(self):
        value, query_type = parse_query_arg("exist:true")
        assert value == "true"
        assert query_type == QueryType.EXIST

    def test_parse_case_insensitive_comparator(self):
        value, query_type = parse_query_arg("EQ:test_value")
        assert value == "test_value"
        assert query_type == QueryType.EQ

    def test_parse_malformed_query_raises_error(self):
        with pytest.raises(ValueError, match="Malformed query string"):
            parse_query_arg("comparator1:comparator2:value")

    def test_parse_unknown_comparator_raises_error(self):
        with pytest.raises(ValueError, match="Unknown query modifier"):
            parse_query_arg("unknown:value")

    def test_parse_colon_in_value_raises_error(self):
        with pytest.raises(ValueError, match="Unknown query modifier"):
            parse_query_arg("http://example.com")

    def test_parse_multiple_colons_in_value_raises_error(self):
        with pytest.raises(ValueError, match="Malformed query string"):
            parse_query_arg("eq:http://example.com")
