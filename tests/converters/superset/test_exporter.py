from pathlib import Path

import pytest

from osi_core.converters.superset import SupersetExporter
from osi_core.serializer import load_osi_yaml

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"
OSI_FIXTURES = FIXTURES / "osi"


@pytest.fixture
def exporter():
    return SupersetExporter()


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
                        "label": "Order ID",
                        "description": "Primary key",
                    },
                    {
                        "name": "created_at",
                        "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "created_at"}]},
                        "dimension": {"is_time": True},
                    },
                    {
                        "name": "status",
                        "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "status"}]},
                        "dimension": {"is_time": False},
                    },
                    {
                        "name": "amount",
                        "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "amount"}]},
                    },
                ],
            }],
            "metrics": [
                {
                    "name": "count",
                    "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "COUNT(*)"}]},
                    "custom_extensions": [
                        {"vendor_name": "SUPERSET", "data": '{"metric_type": "count", "verbose_name": "COUNT(*)"}'}
                    ],
                },
                {
                    "name": "total_revenue",
                    "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "SUM(amount)"}]},
                    "custom_extensions": [
                        {"vendor_name": "SUPERSET", "data": '{"metric_type": "sum", "verbose_name": "Total Revenue"}'}
                    ],
                },
            ],
        }],
    }


class TestDatasetExport:
    def test_creates_table_name(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        assert result["table_name"] == "orders"

    def test_schema_from_source(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        assert result["schema"] == "public"

    def test_sql_is_null_for_table(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        assert result["sql"] is None

    def test_version(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        assert result["version"] == "1.0.0"


class TestColumnExport:
    def test_columns_exported(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        columns = result["columns"]
        names = {c["column_name"] for c in columns}
        assert "created_at" in names
        assert "status" in names
        assert "amount" in names

    def test_time_column_is_dttm(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        col = next(c for c in result["columns"] if c["column_name"] == "created_at")
        assert col["is_dttm"] is True
        assert "TIMESTAMP" in col["type"]

    def test_categorical_column_type(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        col = next(c for c in result["columns"] if c["column_name"] == "status")
        assert col["is_dttm"] is False
        assert col["type"] == "VARCHAR"

    def test_numeric_column_type(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        col = next(c for c in result["columns"] if c["column_name"] == "amount")
        assert col["is_dttm"] is False
        assert col["type"] == "NUMERIC"

    def test_verbose_name_from_label(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        col = next(c for c in result["columns"] if c["column_name"] == "id")
        assert col.get("verbose_name") == "Order ID"


class TestMetricExport:
    def test_metrics_exported(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        metrics = result["metrics"]
        names = {m["metric_name"] for m in metrics}
        assert "count" in names
        assert "total_revenue" in names

    def test_metric_expression(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        m = next(c for c in result["metrics"] if c["metric_name"] == "total_revenue")
        assert m["expression"] == "SUM(amount)"

    def test_metric_type(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        m = next(c for c in result["metrics"] if c["metric_name"] == "total_revenue")
        assert m["metric_type"] == "sum"

    def test_metric_verbose_name(self, exporter):
        result = exporter.from_osi(_minimal_osi())
        m = next(c for c in result["metrics"] if c["metric_name"] == "count")
        assert m.get("verbose_name") == "COUNT(*)"


def test_osi_sample_exports(exporter):
    osi = load_osi_yaml(OSI_FIXTURES / "sample.yaml")
    result = exporter.from_osi(osi)
    assert "table_name" in result
    assert "columns" in result
    assert len(result["columns"]) > 0
