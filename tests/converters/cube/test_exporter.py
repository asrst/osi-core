from pathlib import Path

import pytest

from osi_core.converters.cube import CubeExporter
from osi_core.serializer import load_osi_yaml

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"
OSI_FIXTURES = FIXTURES / "osi"


@pytest.fixture
def exporter():
    return CubeExporter()


def _minimal_osi() -> dict:
    return {
        "version": "0.1.1",
        "semantic_model": [{
            "name": "test_model",
            "datasets": [{
                "name": "orders",
                "source": "public.orders",
                "primary_key": ["id"],
                "fields": [
                    {
                        "name": "id",
                        "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "id"}]},
                        "dimension": {"is_time": False},
                    },
                    {
                        "name": "order_date",
                        "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "order_date"}]},
                        "dimension": {"is_time": True},
                    },
                    {
                        "name": "status",
                        "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "status"}]},
                        "dimension": {"is_time": False},
                    },
                ],
            }],
            "metrics": [
                {
                    "name": "orders__total",
                    "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "SUM(amount)"}]},
                    "custom_extensions": [
                        {"vendor_name": "CUBE", "data": '{"cube_name": "orders", "original_name": "total", "type": "sum"}'}
                    ],
                },
            ],
        }],
    }


class TestCubeExport:
    def test_creates_cubes(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        assert "cubes" in result
        assert len(result["cubes"]) == 1

    def test_cube_name(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        assert cube["name"] == "orders"

    def test_sql_table(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        assert cube["sql_table"] == "public.orders"

    def test_dimensions_exported(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        dims = cube["dimensions"]
        names = {d["name"] for d in dims}
        assert "order_date" in names
        assert "status" in names

    def test_dimension_sql(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        dims = cube["dimensions"]
        status = next(d for d in dims if d["name"] == "status")
        assert status["sql"] == "${CUBE}.status"

    def test_time_dimension_type(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        dims = cube["dimensions"]
        time_dim = next(d for d in dims if d["name"] == "order_date")
        assert time_dim["type"] == "time"

    def test_string_dimension_type(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        dims = cube["dimensions"]
        cat_dim = next(d for d in dims if d["name"] == "status")
        assert cat_dim["type"] == "string"

    def test_primary_key_on_dimension(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        dims = cube["dimensions"]
        id_dim = next(d for d in dims if d["name"] == "id")
        assert id_dim.get("primary_key") is True

    def test_measures_exported(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        measures = cube.get("measures", [])
        assert len(measures) == 1
        assert measures[0]["name"] == "total"

    def test_measure_type(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        measure = cube["measures"][0]
        assert measure["type"] == "sum"

    def test_measure_sql(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        cube = result["cubes"][0]
        measure = cube["measures"][0]
        assert measure["sql"] == "amount"

    def test_measure_count_without_sql(self, exporter):
        osi = _minimal_osi()
        osi["semantic_model"][0]["metrics"] = [
            {
                "name": "orders__order_count",
                "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "COUNT(*)"}]},
                "custom_extensions": [
                    {"vendor_name": "CUBE", "data": '{"cube_name": "orders", "original_name": "order_count", "type": "count"}'}
                ],
            },
        ]
        result = exporter.from_osi(osi)
        cube = result["cubes"][0]
        measure = cube["measures"][0]
        assert measure["type"] == "count"
        assert "sql" not in measure


class TestRelationshipExport:
    def test_relationship_becomes_join(self, exporter):
        osi = _minimal_osi()
        osi["semantic_model"][0]["relationships"] = [
            {
                "name": "orders_to_customers",
                "from": "orders",
                "to": "customers",
                "from_columns": ["customer_id"],
                "to_columns": ["id"],
            },
        ]
        result = exporter.from_osi(osi)
        orders = result["cubes"][0]
        joins = orders.get("joins", [])
        assert len(joins) == 1
        assert joins[0]["name"] == "customers"
        assert "${CUBE}.customer_id" in joins[0]["sql"]
        assert "${customers}.id" in joins[0]["sql"]
        assert "customer_id = ${customers}.id" in joins[0]["sql"].replace("${CUBE}.", "")


def test_osi_sample_exports(exporter):
    osi = load_osi_yaml(OSI_FIXTURES / "sample.yaml")
    result = exporter.from_osi(osi)
    assert "cubes" in result
    assert len(result["cubes"]) > 0
