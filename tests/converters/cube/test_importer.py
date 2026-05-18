from pathlib import Path

import pytest
import yaml

from osi_core.converters.cube import CubeImporter

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures" / "cube"


@pytest.fixture
def importer():
    return CubeImporter()


def load(name: str) -> dict:
    path = FIXTURES / name
    with open(path) as f:
        return yaml.safe_load(f)


class TestBasicCubes:
    def test_parses_name(self, importer):
        result = importer.to_osi(load("orders.yml"))
        sm = result["semantic_model"][0]
        assert sm["name"] == "cube_model"

    def test_creates_datasets(self, importer):
        result = importer.to_osi(load("orders.yml"))
        datasets = result["semantic_model"][0]["datasets"]
        assert len(datasets) == 2
        assert datasets[0]["name"] == "orders"

    def test_extracts_source_from_sql_table(self, importer):
        result = importer.to_osi(load("orders.yml"))
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["source"] == "public.orders"

    def test_primary_key(self, importer):
        result = importer.to_osi(load("orders.yml"))
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["primary_key"] == ["id"]

    def test_dimensions_as_fields(self, importer):
        result = importer.to_osi(load("orders.yml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        names = {f["name"] for f in fields}
        assert "id" in names
        assert "order_date" in names
        assert "status" in names

    def test_time_dimension(self, importer):
        result = importer.to_osi(load("orders.yml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        time_dim = next(f for f in fields if f["name"] == "order_date")
        assert time_dim["dimension"]["is_time"] is True

    def test_string_dimension(self, importer):
        result = importer.to_osi(load("orders.yml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        cat_dim = next(f for f in fields if f["name"] == "status")
        assert cat_dim["dimension"]["is_time"] is False


class TestMeasures:
    def test_measure_becomes_metric(self, importer):
        result = importer.to_osi(load("orders.yml"))
        metrics = result["semantic_model"][0]["metrics"]
        names = {m["name"] for m in metrics}
        assert "orders__total" in names

    def test_sum_measure_expression(self, importer):
        result = importer.to_osi(load("orders.yml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "orders__total")
        expr = m["expression"]["dialects"][0]["expression"]
        assert expr == "SUM(amount)"

    def test_count_measure_expression(self, importer):
        result = importer.to_osi(load("orders.yml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "orders__order_count")
        expr = m["expression"]["dialects"][0]["expression"]
        assert expr == "COUNT(*)"

    def test_avg_measure_expression(self, importer):
        result = importer.to_osi(load("orders.yml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "orders__avg_amount")
        expr = m["expression"]["dialects"][0]["expression"]
        assert expr == "AVG(amount)"

    def test_measure_has_custom_extension(self, importer):
        result = importer.to_osi(load("orders.yml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "orders__total")
        exts = m.get("custom_extensions", [])
        assert any(ext.get("vendor_name") == "CUBE" for ext in exts)
        meta = next(ext for ext in exts if ext["vendor_name"] == "CUBE")
        import json
        data = json.loads(meta["data"])
        assert data["cube_name"] == "orders"
        assert data["original_name"] == "total"


class TestAdvancedMeasures:
    def test_number_type_uses_direct_sql(self, importer):
        result = importer.to_osi(load("advanced.yml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "orders__revenue_ratio")
        expr = m["expression"]["dialects"][0]["expression"]
        assert "SUM(amount)" in expr
        assert "NULLIF" in expr

    def test_count_distinct(self, importer):
        result = importer.to_osi(load("advanced.yml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "orders__count_distinct_customers")
        expr = m["expression"]["dialects"][0]["expression"]
        assert expr == "COUNT(DISTINCT customer_id)"

    def test_window_expression(self, importer):
        result = importer.to_osi(load("advanced.yml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "orders__revenue_running_total")
        expr = m["expression"]["dialects"][0]["expression"]
        assert "OVER" in expr


class TestRelationships:
    def test_join_becomes_relationship(self, importer):
        result = importer.to_osi(load("orders.yml"))
        rels = result["semantic_model"][0]["relationships"]
        assert len(rels) == 1
        assert rels[0]["from"] == "orders"
        assert rels[0]["to"] == "customers"
        assert rels[0]["from_columns"] == ["customer_id"]
        assert rels[0]["to_columns"] == ["id"]

    def test_ecommerce_multiple_relationships(self, importer):
        result = importer.to_osi(load("ecommerce.yml"))
        rels = result["semantic_model"][0]["relationships"]
        assert len(rels) == 2
        to_names = {r["to"] for r in rels}
        assert to_names == {"customers", "products"}


class TestEdgeCases:
    def test_empty_cubes(self, importer):
        result = importer.to_osi({"cubes": []})
        assert result["semantic_model"][0]["datasets"] == []

    def test_cube_without_measures(self, importer):
        result = importer.to_osi({"cubes": [{"name": "empty", "dimensions": []}]})
        assert len(result["semantic_model"][0]["datasets"]) == 1
        assert result["semantic_model"][0]["metrics"] == []
