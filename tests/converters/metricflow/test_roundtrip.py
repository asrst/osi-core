from pathlib import Path

import pytest
import yaml

from osi_core.converters.metricflow import DbtMetricFlowConverter

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures" / "metricflow"


@pytest.fixture
def converter():
    return DbtMetricFlowConverter()


def load(name: str) -> dict:
    path = FIXTURES / name
    with open(path) as f:
        return yaml.safe_load(f)


class TestRoundtrip:
    def test_basic_roundtrip(self, converter):
        original = load("basic.yaml")
        osi = converter.to_osi(original)
        exported = converter.from_osi(osi)

        assert "semantic_models" in exported
        assert len(exported["semantic_models"]) == 2
        assert exported["semantic_models"][0]["name"] == "orders"

    def test_ecommerce_roundtrip(self, converter):
        original = load("ecommerce.yaml")
        osi = converter.to_osi(original)
        exported = converter.from_osi(osi)

        names = {sm["name"] for sm in exported["semantic_models"]}
        assert names == {"orders", "customers", "products"}

    def test_advanced_metrics_roundtrip(self, converter):
        original = load("advanced_metrics.yaml")
        osi = converter.to_osi(original)
        exported = converter.from_osi(osi)

        metric_names = {m["name"] for m in exported.get("metrics", [])}
        assert "revenue_per_order" in metric_names
        assert "revenue_growth" in metric_names
        assert "revenue_mtd" in metric_names

    def test_roundtrip_creates_valid_osi(self, converter):
        original = load("basic.yaml")
        osi = converter.to_osi(original)
        assert "version" in osi
        assert "semantic_model" in osi
        assert len(osi["semantic_model"][0]["datasets"]) > 0
        assert len(osi["semantic_model"][0]["metrics"]) > 0
