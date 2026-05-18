"""Tests for the OSI to Snowflake YAML converter (exporter)."""

import warnings

import pytest
import yaml

from osi_core.converters.snowflake.exporter import (
    OsiConversionError,
    SnowflakeExporter,
    _classify_field,
    _extract_expression,
    _extract_synonyms,
    _parse_source,
)
from osi_core.normalizer import normalize_identifier as _normalize_identifier


@pytest.fixture
def exporter():
    return SnowflakeExporter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wrap_osi(model_dict):
    return {"version": "0.1.1", "semantic_model": [model_dict]}


def _minimal_model(**overrides):
    base = {
        "name": "test_model",
        "datasets": [
            {
                "name": "my_table",
                "source": "db.schema.tbl",
                "fields": [
                    {
                        "name": "col1",
                        "expression": {
                            "dialects": [
                                {"dialect": "ANSI_SQL", "expression": "col1"}
                            ]
                        },
                        "dimension": {"is_time": False},
                    }
                ],
            }
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _normalize_identifier
# ---------------------------------------------------------------------------


class TestNormalizeIdentifier:
    def test_unquoted_uppercased(self):
        assert _normalize_identifier("my_table") == "MY_TABLE"

    def test_quoted_preserved(self):
        assert _normalize_identifier('"My Table"') == '"My Table"'

    def test_whitespace_stripped(self):
        assert _normalize_identifier("  foo  ") == "FOO"

    def test_quoted_whitespace_stripped(self):
        assert _normalize_identifier('  "bar"  ') == '"bar"'


# ---------------------------------------------------------------------------
# _parse_source
# ---------------------------------------------------------------------------


class TestParseSource:
    def test_three_part_name(self):
        result = _parse_source("db.schema.table")
        assert result == {"database": "DB", "schema": "SCHEMA", "table": "TABLE"}

    def test_quoted_identifiers_preserved(self):
        result = _parse_source('"myDb"."mySchema"."myTable"')
        assert result == {
            "database": '"myDb"',
            "schema": '"mySchema"',
            "table": '"myTable"',
        }

    def test_subquery_select(self):
        result = _parse_source("SELECT * FROM foo")
        assert result == {"definition": "SELECT * FROM foo"}

    def test_subquery_with(self):
        result = _parse_source("WITH cte AS (SELECT 1) SELECT * FROM cte")
        assert result == {"definition": "WITH cte AS (SELECT 1) SELECT * FROM cte"}

    def test_none_returns_none(self):
        assert _parse_source(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_source("") is None

    def test_whitespace_only_returns_none(self):
        assert _parse_source("   ") is None

    def test_two_part_name_raises(self):
        with pytest.raises(OsiConversionError, match="fully qualified"):
            _parse_source("schema.table")

    def test_one_part_name_raises(self):
        with pytest.raises(OsiConversionError, match="fully qualified"):
            _parse_source("table")

    def test_table_starting_with_select_not_subquery(self):
        with pytest.raises(OsiConversionError, match="fully qualified"):
            _parse_source("SELECT_RESULTS")


# ---------------------------------------------------------------------------
# _extract_synonyms
# ---------------------------------------------------------------------------


class TestExtractSynonyms:
    def test_dict_with_synonyms(self):
        assert _extract_synonyms({"synonyms": ["a", "b"]}) == ["a", "b"]

    def test_dict_without_synonyms(self):
        assert _extract_synonyms({"instructions": "foo"}) is None

    def test_empty_synonyms_list(self):
        assert _extract_synonyms({"synonyms": []}) is None

    def test_string_ai_context(self):
        assert _extract_synonyms("some instructions") is None

    def test_none(self):
        assert _extract_synonyms(None) is None

    def test_returns_copy(self):
        original = ["x", "y"]
        result = _extract_synonyms({"synonyms": original})
        assert result == original
        assert result is not original


# ---------------------------------------------------------------------------
# _classify_field
# ---------------------------------------------------------------------------


class TestClassifyField:
    def test_no_dimension_is_fact(self):
        assert _classify_field({"name": "x"}) == "fact"

    def test_dimension_not_time(self):
        assert _classify_field({"dimension": {"is_time": False}}) == "dimension"

    def test_dimension_is_time(self):
        assert _classify_field({"dimension": {"is_time": True}}) == "time_dimension"

    def test_dimension_bare_true(self):
        assert _classify_field({"dimension": True}) == "dimension"

    def test_dimension_none_is_fact(self):
        assert _classify_field({"dimension": None}) == "fact"


# ---------------------------------------------------------------------------
# _extract_expression
# ---------------------------------------------------------------------------


class TestExtractExpression:
    def test_snowflake_preferred_over_ansi(self):
        expr = {
            "dialects": [
                {"dialect": "ANSI_SQL", "expression": "ansi_expr"},
                {"dialect": "SNOWFLAKE", "expression": "snow_expr"},
            ]
        }
        assert _extract_expression(expr, "f") == "snow_expr"

    def test_ansi_fallback(self):
        expr = {"dialects": [{"dialect": "ANSI_SQL", "expression": "ansi_expr"}]}
        assert _extract_expression(expr, "f") == "ansi_expr"

    def test_unsupported_dialect_returns_none_with_warning(self):
        expr = {"dialects": [{"dialect": "BIGQUERY", "expression": "bq_expr"}]}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _extract_expression(expr, "my_field")
        assert result is None
        assert len(w) == 1
        assert "my_field" in str(w[0].message)

    def test_missing_expression_raises(self):
        with pytest.raises(OsiConversionError, match="Missing or malformed"):
            _extract_expression(None, "f")

    def test_missing_dialects_raises(self):
        with pytest.raises(OsiConversionError, match="Missing expression"):
            _extract_expression({"dialects": []}, "f")

    def test_empty_dialects_raises(self):
        with pytest.raises(OsiConversionError, match="Missing expression"):
            _extract_expression({"dialects": None}, "f")


# ---------------------------------------------------------------------------
# SnowflakeExporter.from_osi
# ---------------------------------------------------------------------------


class TestSnowflakeExporter:
    def test_minimal_model(self, exporter):
        osi = _wrap_osi(_minimal_model())
        result = exporter.from_osi(osi)
        assert result["name"] == "test_model"
        assert "tables" in result
        assert result["tables"][0]["name"] == "my_table"

    def test_model_with_description(self, exporter):
        osi = _wrap_osi(_minimal_model(description="A model"))
        result = exporter.from_osi(osi)
        assert result["description"] == "A model"

    def test_model_with_relationships(self, exporter):
        model = _minimal_model(
            relationships=[
                {
                    "name": "r1",
                    "from": "a",
                    "to": "b",
                    "from_columns": ["x"],
                    "to_columns": ["y"],
                }
            ]
        )
        result = exporter.from_osi(_wrap_osi(model))
        assert len(result["relationships"]) == 1
        assert result["relationships"][0]["name"] == "r1"

    def test_model_with_metrics(self, exporter):
        model = _minimal_model(
            metrics=[
                {
                    "name": "total",
                    "expression": {
                        "dialects": [
                            {"dialect": "ANSI_SQL", "expression": "SUM(x)"}
                        ]
                    },
                    "description": "Total x",
                }
            ]
        )
        result = exporter.from_osi(_wrap_osi(model))
        assert len(result["metrics"]) == 1
        assert result["metrics"][0]["expr"] == "SUM(x)"

    def test_wrong_version_raises(self, exporter):
        bad = {"version": "9.9.9", "semantic_model": [{"name": "m"}]}
        with pytest.raises(OsiConversionError, match="Unsupported OSI specification"):
            exporter.from_osi(bad)

    def test_missing_semantic_model_raises(self, exporter):
        bad = {"version": "0.1.1"}
        with pytest.raises(OsiConversionError, match="Missing 'semantic_model'"):
            exporter.from_osi(bad)

    def test_empty_semantic_model_raises(self, exporter):
        bad = {"version": "0.1.1", "semantic_model": []}
        with pytest.raises(OsiConversionError, match="Missing 'semantic_model'"):
            exporter.from_osi(bad)

    def test_missing_model_name_raises(self, exporter):
        bad = {"version": "0.1.1", "semantic_model": [{"description": "x"}]}
        with pytest.raises(OsiConversionError, match="Missing required 'name'"):
            exporter.from_osi(bad)

    def test_multiple_models_warns(self, exporter):
        multi = {
            "version": "0.1.1",
            "semantic_model": [
                _minimal_model(name="first"),
                _minimal_model(name="second"),
            ],
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = exporter.from_osi(multi)
        assert result["name"] == "first"
        assert any("only the first" in str(warning.message) for warning in w)

    def test_snowflake_dialect_preferred(self, exporter):
        model = {
            "name": "m",
            "datasets": [
                {
                    "name": "t",
                    "source": "db.s.t",
                    "fields": [
                        {
                            "name": "c",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "ansi_c"},
                                    {"dialect": "SNOWFLAKE", "expression": "snow_c"},
                                ]
                            },
                            "dimension": {"is_time": False},
                        }
                    ],
                }
            ],
        }
        result = exporter.from_osi(_wrap_osi(model))
        assert result["tables"][0]["dimensions"][0]["expr"] == "snow_c"

    def test_fields_with_unsupported_dialect_skipped(self, exporter):
        model = {
            "name": "m",
            "datasets": [
                {
                    "name": "t",
                    "source": "db.s.t",
                    "fields": [
                        {
                            "name": "good",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "good"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        },
                        {
                            "name": "bad",
                            "expression": {
                                "dialects": [
                                    {"dialect": "BIGQUERY", "expression": "bad"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        },
                    ],
                }
            ],
        }
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = exporter.from_osi(_wrap_osi(model))
        dims = result["tables"][0]["dimensions"]
        assert len(dims) == 1
        assert dims[0]["name"] == "good"

    def test_subquery_source(self, exporter):
        model = {
            "name": "m",
            "datasets": [
                {
                    "name": "t",
                    "source": "SELECT * FROM db.s.t WHERE active = 1",
                    "fields": [
                        {
                            "name": "c",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "c"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        }
                    ],
                }
            ],
        }
        result = exporter.from_osi(_wrap_osi(model))
        assert "definition" in result["tables"][0]["base_table"]

    def test_custom_extensions_dropped_with_warning(self, exporter):
        model = _minimal_model(
            custom_extensions=[{"vendor_name": "X", "data": "{}"}]
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = exporter.from_osi(_wrap_osi(model))
        assert "custom_extensions" not in result
        assert any("custom_extensions" in str(x.message) for x in w)

    def test_model_level_ai_context_dropped_with_warning(self, exporter):
        model = _minimal_model(
            ai_context={"instructions": "use this model for analytics"}
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = exporter.from_osi(_wrap_osi(model))
        assert "ai_context" not in result
        assert any("ai_context" in str(x.message) for x in w)

    def test_relationship_ai_context_dropped_with_warning(self, exporter):
        model = _minimal_model(
            relationships=[
                {
                    "name": "r1",
                    "from": "a",
                    "to": "b",
                    "from_columns": ["x"],
                    "to_columns": ["y"],
                    "ai_context": {"synonyms": ["related"]},
                }
            ]
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = exporter.from_osi(_wrap_osi(model))
        rel = result["relationships"][0]
        assert "ai_context" not in rel
        assert "synonyms" not in rel
        assert any("ai_context" in str(x.message) for x in w)

    def test_model_string_ai_context_appended_to_description(self, exporter):
        model = _minimal_model(
            description="A model",
            ai_context="use this model for analytics",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = exporter.from_osi(_wrap_osi(model))
        assert result["description"] == "A model\nuse this model for analytics"
        assert not any("ai_context" in str(x.message) for x in w)

    def test_field_label_dropped_with_warning(self, exporter):
        model = {
            "name": "m",
            "datasets": [
                {
                    "name": "t",
                    "source": "db.s.t",
                    "fields": [
                        {
                            "name": "c",
                            "label": "My Column",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "c"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        }
                    ],
                }
            ],
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = exporter.from_osi(_wrap_osi(model))
        dim = result["tables"][0]["dimensions"][0]
        assert "label" not in dim
        assert any("label" in str(x.message) for x in w)
