from pathlib import Path

import pytest
import yaml

from osi_core.converters.metricflow import DbtMetricFlowExporter
from osi_core.serializer import load_osi_yaml

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"
OSI_FIXTURES = FIXTURES / "osi"


@pytest.fixture
def exporter():
    return DbtMetricFlowExporter()


def _minimal_osi() -> dict:
    return {
        "version": "0.1.1",
        "semantic_model": [{
            "name": "test_model",
            "datasets": [{
                "name": "orders",
                "source": "raw_orders",
                "primary_key": ["order_id"],
                "fields": [
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
                    "name": "order_total",
                    "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "SUM(amount)"}]},
                    "custom_extensions": [
                        {"vendor_name": "DBT_METRICFLOW", "data": '{"kind": "measure", "measure_source": "orders", "agg": "sum"}'}
                    ],
                },
            ],
        }],
    }


class TestSemanticModelExport:
    def test_creates_semantic_models(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        assert "semantic_models" in result
        assert len(result["semantic_models"]) == 1

    def test_semantic_model_name(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        sm = result["semantic_models"][0]
        assert sm["name"] == "orders"

    def test_source_wrapped_in_ref(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        sm = result["semantic_models"][0]
        assert sm["model"] == "ref('raw_orders')"

    def test_primary_entity(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        sm = result["semantic_models"][0]
        entities = sm["entities"]
        assert any(e["type"] == "primary" and e["expr"] == "order_id" for e in entities)


class TestDimensionExport:
    def test_time_dimension(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        sm = result["semantic_models"][0]
        dims = sm["dimensions"]
        time_dim = next(d for d in dims if d["name"] == "order_date")
        assert time_dim["type"] == "time"

    def test_categorical_dimension(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        sm = result["semantic_models"][0]
        dims = sm["dimensions"]
        cat_dim = next(d for d in dims if d["name"] == "status")
        assert cat_dim["type"] == "categorical"


class TestRelationshipExport:
    def test_relationship_becomes_entity(self, exporter):
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
        osi["semantic_model"][0]["datasets"].append({
            "name": "customers",
            "source": "raw_customers",
            "primary_key": ["id"],
            "fields": [],
        })
        result = exporter.from_osi(osi)
        orders_sm = next(sm for sm in result["semantic_models"] if sm["name"] == "orders")
        entities = orders_sm["entities"]
        assert any(e["name"] == "customers" and e["type"] == "foreign" for e in entities)


class TestMetricExport:
    def test_measure_not_in_metrics_list(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        assert "metrics" not in result or len(result.get("metrics", [])) == 0

    def test_ratio_metric_exported(self, exporter):
        osi = _minimal_osi()
        osi["semantic_model"][0]["metrics"].append({
            "name": "revenue_per_order",
            "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "order_total / NULLIF(order_count, 0)"}]},
            "custom_extensions": [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": '{"kind": "metric", "metric_type": "ratio", "numerator": "order_total", "denominator": "order_count"}',
                }
            ],
        })
        result = exporter.from_osi(osi)
        metrics = result.get("metrics", [])
        ratio = next(m for m in metrics if m["name"] == "revenue_per_order")
        assert ratio["type"] == "ratio"
        assert ratio["type_params"]["numerator"]["name"] == "order_total"

    def test_derived_metric_exported(self, exporter):
        osi = _minimal_osi()
        osi["semantic_model"][0]["metrics"].append({
            "name": "revenue_growth",
            "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "total_revenue / NULLIF(revenue_last_year, 0)"}]},
            "custom_extensions": [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": '{"kind": "metric", "metric_type": "derived"}',
                }
            ],
        })
        result = exporter.from_osi(osi)
        metrics = result.get("metrics", [])
        derived = next(m for m in metrics if m["name"] == "revenue_growth")
        assert derived["type"] == "derived"

    def test_cumulative_metric_exported(self, exporter):
        osi = _minimal_osi()
        osi["semantic_model"][0]["metrics"].append({
            "name": "revenue_mtd",
            "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "order_total"}]},
            "custom_extensions": [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": '{"kind": "metric", "metric_type": "cumulative", "measure": "order_total", "window": "30 days", "grain_to_date": "day"}',
                }
            ],
        })
        result = exporter.from_osi(osi)
        metrics = result.get("metrics", [])
        cum = next(m for m in metrics if m["name"] == "revenue_mtd")
        assert cum["type"] == "cumulative"
        assert cum["type_params"]["window"] == "30 days"


def test_osi_sample_exports(exporter):
    osi = load_osi_yaml(OSI_FIXTURES / "sample.yaml")
    result = exporter.from_osi(osi)
    assert "semantic_models" in result
    assert len(result["semantic_models"]) > 0
