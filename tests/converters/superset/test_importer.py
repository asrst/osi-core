from pathlib import Path

import pytest
import yaml

from osi_core.converters.superset import SupersetImporter

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures" / "superset"


@pytest.fixture
def importer():
    return SupersetImporter()


def load(name: str) -> dict:
    path = FIXTURES / name
    with open(path) as f:
        return yaml.safe_load(f)


class TestBasicDataset:
    def test_parses_table_name(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        sm = result["semantic_model"][0]
        assert sm["name"] == "orders"

    def test_creates_dataset(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        datasets = result["semantic_model"][0]["datasets"]
        assert len(datasets) == 1
        assert datasets[0]["name"] == "orders"

    def test_source_with_schema(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["source"] == "public.orders"

    def test_primary_key(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["primary_key"] == ["id"]


class TestColumnsAsFields:
    def test_creates_fields(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        names = {f["name"] for f in fields}
        assert "id" in names
        assert "status" in names
        assert "amount" in names

    def test_time_dimension_from_is_dttm(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        time_f = next(f for f in fields if f["name"] == "created_at")
        assert time_f["dimension"]["is_time"] is True

    def test_categorical_dimension(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        cat_f = next(f for f in fields if f["name"] == "status")
        assert cat_f["dimension"]["is_time"] is False

    def test_numeric_column_no_dimension(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        num_f = next(f for f in fields if f["name"] == "amount")
        assert "dimension" not in num_f

    def test_verbose_name_becomes_label(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        id_f = next(f for f in fields if f["name"] == "id")
        assert id_f.get("label") == "Order ID"

    def test_description_preserved(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        id_f = next(f for f in fields if f["name"] == "id")
        assert id_f.get("description") == "Primary key"


class TestComputedColumns:
    def test_computed_column_uses_expression(self, importer):
        result = importer.to_osi(load("ecommerce_products.yaml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        margin = next(f for f in fields if f["name"] == "margin_pct")
        expr = margin["expression"]["dialects"][0]["expression"]
        assert "price - cost" in expr
        assert "NULLIF" in expr


class TestMetrics:
    def test_creates_metrics(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        names = {m["name"] for m in metrics}
        assert "count" in names
        assert "total_revenue" in names

    def test_metric_expression(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(_m for _m in metrics if _m["name"] == "total_revenue")
        expr = m["expression"]["dialects"][0]["expression"]
        assert expr == "SUM(amount)"

    def test_derived_metric_no_type(self, importer):
        result = importer.to_osi(load("ecommerce_products.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        avg_margin = next(m for m in metrics if m["name"] == "avg_margin")
        expr = avg_margin["expression"]["dialects"][0]["expression"]
        assert "AVG" in expr

    def test_metric_custom_extension_type(self, importer):
        result = importer.to_osi(load("orders.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(_m for _m in metrics if _m["name"] == "total_revenue")
        exts = m.get("custom_extensions", [])
        assert any(ext.get("vendor_name") == "SUPERSET" for ext in exts)


class TestEdgeCases:
    def test_empty_columns(self, importer):
        result = importer.to_osi({"table_name": "empty", "columns": []})
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["fields"] == []

    def test_empty_metrics(self, importer):
        result = importer.to_osi({"table_name": "empty", "columns": [{"column_name": "c"}], "metrics": []})
        assert result["semantic_model"][0]["metrics"] == []

    def test_boolean_column_is_dimension(self, importer):
        result = importer.to_osi({
            "table_name": "t",
            "columns": [{"column_name": "active", "type": "BOOLEAN"}],
        })
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        assert fields[0]["dimension"]["is_time"] is False
