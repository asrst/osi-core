"""Tests for Snowflake → OSI conversion (importer)."""

import pytest
import yaml

from osi_core.converters.snowflake.importer import SnowflakeImporter


@pytest.fixture
def importer():
    return SnowflakeImporter()


def _minimal_snowflake(**overrides):
    base = {
        "name": "test_model",
        "tables": [
            {
                "name": "my_table",
                "base_table": {
                    "database": "DB",
                    "schema": "SCHEMA",
                    "table": "TBL",
                },
                "dimensions": [
                    {"name": "col1", "expr": "col1"},
                ],
            }
        ],
    }
    base.update(overrides)
    return base


class TestSnowflakeImporter:
    def test_minimal_import(self, importer):
        sf = _minimal_snowflake()
        result = importer.to_osi(sf)
        assert result["version"] == "0.1.1"
        assert len(result["semantic_model"]) == 1
        sm = result["semantic_model"][0]
        assert sm["name"] == "test_model"
        assert len(sm["datasets"]) == 1
        assert sm["datasets"][0]["name"] == "my_table"

    def test_source_reconstructed(self, importer):
        sf = _minimal_snowflake()
        result = importer.to_osi(sf)
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["source"] == "db.schema.tbl"

    def test_field_conversion_dimension(self, importer):
        sf = _minimal_snowflake()
        result = importer.to_osi(sf)
        ds = result["semantic_model"][0]["datasets"][0]
        field = ds["fields"][0]
        assert field["name"] == "col1"
        assert field["dimension"] == {"is_time": False}

    def test_field_conversion_time_dimension(self, importer):
        sf = {
            "name": "m",
            "tables": [
                {
                    "name": "t",
                    "time_dimensions": [
                        {"name": "created_at", "expr": "created_at"}
                    ],
                }
            ],
        }
        result = importer.to_osi(sf)
        field = result["semantic_model"][0]["datasets"][0]["fields"][0]
        assert field["dimension"] == {"is_time": True}

    def test_field_conversion_fact(self, importer):
        sf = {
            "name": "m",
            "tables": [
                {
                    "name": "t",
                    "facts": [
                        {"name": "amount", "expr": "amount"}
                    ],
                }
            ],
        }
        result = importer.to_osi(sf)
        field = result["semantic_model"][0]["datasets"][0]["fields"][0]
        assert "dimension" not in field

    def test_primary_key(self, importer):
        sf = {
            "name": "m",
            "tables": [
                {
                    "name": "t",
                    "base_table": {"database": "DB", "schema": "S", "table": "T"},
                    "primary_key": {"columns": ["id"]},
                    "dimensions": [{"name": "id", "expr": "id"}],
                }
            ],
        }
        result = importer.to_osi(sf)
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["primary_key"] == ["id"]

    def test_unique_keys(self, importer):
        sf = {
            "name": "m",
            "tables": [
                {
                    "name": "t",
                    "base_table": {"database": "DB", "schema": "S", "table": "T"},
                    "unique_keys": [{"columns": ["email"]}],
                    "dimensions": [{"name": "email", "expr": "email"}],
                }
            ],
        }
        result = importer.to_osi(sf)
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["unique_keys"] == [["email"]]

    def test_relationships(self, importer):
        sf = {
            "name": "m",
            "tables": [
                {
                    "name": "a",
                    "base_table": {"database": "DB", "schema": "S", "table": "A"},
                    "dimensions": [{"name": "id", "expr": "id"}],
                },
                {
                    "name": "b",
                    "base_table": {"database": "DB", "schema": "S", "table": "B"},
                    "dimensions": [{"name": "id", "expr": "id"}],
                },
            ],
            "relationships": [
                {
                    "name": "a_to_b",
                    "left_table": "a",
                    "right_table": "b",
                    "relationship_columns": [
                        {"left_column": "a_id", "right_column": "b_id"}
                    ],
                }
            ],
        }
        result = importer.to_osi(sf)
        sm = result["semantic_model"][0]
        assert len(sm["relationships"]) == 1
        rel = sm["relationships"][0]
        assert rel["from"] == "a"
        assert rel["to"] == "b"
        assert rel["from_columns"] == ["a_id"]
        assert rel["to_columns"] == ["b_id"]

    def test_metrics(self, importer):
        sf = {
            "name": "m",
            "tables": [
                {
                    "name": "t",
                    "base_table": {"database": "DB", "schema": "S", "table": "T"},
                    "dimensions": [{"name": "id", "expr": "id"}],
                }
            ],
            "metrics": [
                {"name": "total", "expr": "SUM(id)", "description": "Total"}
            ],
        }
        result = importer.to_osi(sf)
        sm = result["semantic_model"][0]
        assert len(sm["metrics"]) == 1
        metric = sm["metrics"][0]
        assert metric["name"] == "total"
        assert metric["expression"]["dialects"][0]["expression"] == "SUM(id)"

    def test_synonyms(self, importer):
        sf = {
            "name": "m",
            "tables": [
                {
                    "name": "t",
                    "base_table": {"database": "DB", "schema": "S", "table": "T"},
                    "synonyms": ["table", "tbl"],
                    "dimensions": [
                        {
                            "name": "c",
                            "expr": "c",
                            "synonyms": ["col", "column"],
                        }
                    ],
                }
            ],
        }
        result = importer.to_osi(sf)
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["ai_context"]["synonyms"] == ["table", "tbl"]
        assert ds["fields"][0]["ai_context"]["synonyms"] == ["col", "column"]

    def test_subquery_source(self, importer):
        sf = {
            "name": "m",
            "tables": [
                {
                    "name": "t",
                    "base_table": {"definition": "SELECT * FROM db.s.t WHERE active = 1"},
                    "dimensions": [{"name": "c", "expr": "c"}],
                }
            ],
        }
        result = importer.to_osi(sf)
        ds = result["semantic_model"][0]["datasets"][0]
        assert "SELECT" in ds["source"]

    def test_description(self, importer):
        sf = {
            "name": "m",
            "tables": [
                {
                    "name": "t",
                    "base_table": {"database": "DB", "schema": "S", "table": "T"},
                    "description": "A table",
                    "dimensions": [{"name": "c", "expr": "c"}],
                }
            ],
        }
        result = importer.to_osi(sf)
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["description"] == "A table"
