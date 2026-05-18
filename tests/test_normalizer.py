from __future__ import annotations

from osi_core.normalizer import (
    normalize_identifier,
    parse_source,
    pick_best_dialect,
    coerce_to_dialect_expression,
)
from osi_core.models.types import Dialect, DialectExpr, DialectExpression


class TestNormalizeIdentifier:
    def test_unquoted_uppercased(self):
        assert normalize_identifier("my_table") == "MY_TABLE"

    def test_quoted_preserved(self):
        assert normalize_identifier('"My Table"') == '"My Table"'

    def test_whitespace_stripped(self):
        assert normalize_identifier("  foo  ") == "FOO"

    def test_quoted_whitespace_stripped(self):
        assert normalize_identifier('  "bar"  ') == '"bar"'


class TestParseSource:
    def test_three_part_name(self):
        result = parse_source("db.schema.table")
        assert result == {"database": "db", "schema": "schema", "table": "table"}

    def test_two_part_name(self):
        result = parse_source("schema.table")
        assert result == {"database": None, "schema": "schema", "table": "table"}

    def test_one_part_name(self):
        result = parse_source("table")
        assert result == {"database": None, "schema": None, "table": "table"}

    def test_empty_string(self):
        result = parse_source("")
        assert result == {"database": None, "schema": None, "table": ""}


class TestPickBestDialect:
    def test_preferred_dialect_selected(self):
        expr = {
            "dialects": [
                {"dialect": "ANSI_SQL", "expression": "ansi_expr"},
                {"dialect": "SNOWFLAKE", "expression": "snow_expr"},
            ]
        }
        result = pick_best_dialect(expr, preferred=[Dialect.SNOWFLAKE])
        assert result is not None
        assert result.dialect == Dialect.SNOWFLAKE
        assert result.expression == "snow_expr"

    def test_default_preference(self):
        expr = {
            "dialects": [
                {"dialect": "SNOWFLAKE", "expression": "snow_expr"},
                {"dialect": "ANSI_SQL", "expression": "ansi_expr"},
            ]
        }
        result = pick_best_dialect(expr)
        assert result is not None
        assert result.dialect == Dialect.SNOWFLAKE

    def test_ansi_fallback(self):
        expr = {"dialects": [{"dialect": "ANSI_SQL", "expression": "ansi_expr"}]}
        result = pick_best_dialect(expr, preferred=[Dialect.SNOWFLAKE])
        assert result is not None
        assert result.expression == "ansi_expr"

    def test_plain_string_expression(self):
        result = pick_best_dialect("simple_column")
        assert result is not None
        assert result.dialect == Dialect.ANSI_SQL
        assert result.expression == "simple_column"

    def test_unsupported_dialect_returns_none(self):
        expr = {"dialects": [{"dialect": "BIGQUERY", "expression": "bq_expr"}]}
        result = pick_best_dialect(expr, preferred=[Dialect.SNOWFLAKE])
        assert result is None


class TestCoerceToDialectExpression:
    def test_creates_dialect_expression(self):
        result = coerce_to_dialect_expression("SELECT 1", Dialect.ANSI_SQL)
        assert result == DialectExpression(
            dialects=[DialectExpr(dialect=Dialect.ANSI_SQL, expression="SELECT 1")]
        )

    def test_default_dialect(self):
        result = coerce_to_dialect_expression("SELECT 1")
        assert result.dialects[0].dialect == Dialect.ANSI_SQL
