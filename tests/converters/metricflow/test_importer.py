from pathlib import Path

import pytest
import yaml

from osi_core.converters.metricflow import DbtMetricFlowImporter

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures" / "metricflow"


@pytest.fixture
def importer():
    return DbtMetricFlowImporter()


def load(name: str) -> dict:
    path = FIXTURES / name
    with open(path) as f:
        return yaml.safe_load(f)


class TestBasicSemanticModel:
    def test_parses_name(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        sm = result["semantic_model"][0]
        assert sm["name"] == "metricflow_model"

    def test_creates_dataset(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        datasets = result["semantic_model"][0]["datasets"]
        assert len(datasets) == 2
        assert datasets[0]["name"] == "orders"

    def test_extracts_source_from_ref(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["source"] == "raw_orders"

    def test_primary_key_from_entity(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        ds = result["semantic_model"][0]["datasets"][0]
        assert ds["primary_key"] == ["order_id"]

    def test_dimensions_as_fields(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        assert len(fields) == 4  # 2 dims + customer_id (foreign entity) + order_id (PK entity)

        time_dim = next(f for f in fields if f["name"] == "order_date")
        assert time_dim["dimension"]["is_time"] is True

        cat_dim = next(f for f in fields if f["name"] == "status")
        assert cat_dim["dimension"]["is_time"] is False

    def test_time_dimension_granularity(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        fields = result["semantic_model"][0]["datasets"][0]["fields"]
        time_dim = next(f for f in fields if f["name"] == "order_date")
        exts = time_dim.get("custom_extensions", [])
        assert any("day" in ext["data"] for ext in exts)


class TestMeasures:
    def test_measure_becomes_metric(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        assert any(m["name"] == "order_total" for m in metrics)

    def test_sum_measure_expression(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "order_total")
        expr = m["expression"]["dialects"][0]["expression"]
        assert expr == "SUM(amount)"

    def test_count_measure_expression(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "order_count")
        expr = m["expression"]["dialects"][0]["expression"]
        assert expr == "COUNT(*)"

    def test_measure_has_custom_extension(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        m = next(m for m in metrics if m["name"] == "order_total")
        exts = m.get("custom_extensions", [])
        assert any(ext.get("vendor_name") == "DBT_METRICFLOW" for ext in exts)


class TestRelationships:
    def test_foreign_entity_becomes_relationship(self, importer):
        result = importer.to_osi(load("basic.yaml"))
        rels = result["semantic_model"][0]["relationships"]
        assert len(rels) == 1
        assert rels[0]["from"] == "orders"
        assert rels[0]["to"] == "customers"
        assert rels[0]["from_columns"] == ["customer_id"]

    def test_ecommerce_multiple_relationships(self, importer):
        result = importer.to_osi(load("ecommerce.yaml"))
        rels = result["semantic_model"][0]["relationships"]
        assert len(rels) == 2
        to_names = {r["to"] for r in rels}
        assert to_names == {"customers", "products"}


class TestAdvancedMetrics:
    def test_simple_metric(self, importer):
        result = importer.to_osi(load("advanced_metrics.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        names = {m["name"] for m in metrics}
        assert "total_revenue" in names
        assert "order_count" in names

    def test_ratio_metric(self, importer):
        result = importer.to_osi(load("advanced_metrics.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        ratio = next(m for m in metrics if m["name"] == "revenue_per_order")
        expr = ratio["expression"]["dialects"][0]["expression"]
        assert "order_total" in expr
        assert "NULLIF" in expr

    def test_derived_metric(self, importer):
        result = importer.to_osi(load("advanced_metrics.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        derived = next(m for m in metrics if m["name"] == "revenue_growth")
        expr = derived["expression"]["dialects"][0]["expression"]
        assert "total_revenue" in expr

    def test_cumulative_metric(self, importer):
        result = importer.to_osi(load("advanced_metrics.yaml"))
        metrics = result["semantic_model"][0]["metrics"]
        cum = next(m for m in metrics if m["name"] == "revenue_mtd")
        expr = cum["expression"]["dialects"][0]["expression"]
        assert expr == "order_total"

    def test_empty_semantic_models(self, importer):
        result = importer.to_osi({"semantic_models": []})
        assert result["semantic_model"][0]["datasets"] == []

    def test_empty_metrics(self, importer):
        result = importer.to_osi({"semantic_models": [], "metrics": []})
        assert result["semantic_model"][0]["metrics"] == []
