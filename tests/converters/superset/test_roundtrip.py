from pathlib import Path

import pytest
import yaml

from osi_core.converters.superset import SupersetConverter

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures" / "superset"


@pytest.fixture
def converter():
    return SupersetConverter()


def load(name: str) -> dict:
    path = FIXTURES / name
    with open(path) as f:
        return yaml.safe_load(f)


class TestRoundtrip:
    def test_basic_roundtrip(self, converter):
        original = load("orders.yaml")
        osi = converter.to_osi(original)
        exported = converter.from_osi(osi)

        assert exported["table_name"] == "orders"
        assert exported["schema"] == "public"
        assert len(exported["columns"]) > 0
        assert len(exported["metrics"]) > 0

    def test_ecommerce_roundtrip(self, converter):
        original = load("ecommerce_products.yaml")
        osi = converter.to_osi(original)
        exported = converter.from_osi(osi)

        assert exported["table_name"] == "ecommerce_products"
        metric_names = {m["metric_name"] for m in exported.get("metrics", [])}
        assert "total_revenue" in metric_names
        assert "avg_margin" in metric_names

    def test_sales_dashboard_roundtrip(self, converter):
        original = load("sales_dashboard.yaml")
        osi = converter.to_osi(original)
        exported = converter.from_osi(osi)

        assert exported["table_name"] == "cleaned_sales_data"
        column_names = {c["column_name"] for c in exported.get("columns", [])}
        assert "order_date" in column_names
        assert "sales" in column_names

    def test_roundtrip_creates_valid_osi(self, converter):
        original = load("orders.yaml")
        osi = converter.to_osi(original)
        assert "version" in osi
        assert "semantic_model" in osi
        assert len(osi["semantic_model"][0]["datasets"]) > 0
