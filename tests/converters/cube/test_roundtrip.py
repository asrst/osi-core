from pathlib import Path

import pytest
import yaml

from osi_core.converters.cube import CubeConverter

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures" / "cube"


@pytest.fixture
def converter():
    return CubeConverter()


def load(name: str) -> dict:
    path = FIXTURES / name
    with open(path) as f:
        return yaml.safe_load(f)


class TestRoundtrip:
    def test_basic_roundtrip(self, converter):
        original = load("orders.yaml")
        osi = converter.to_osi(original)
        exported = converter.from_osi(osi)

        assert "cubes" in exported
        assert len(exported["cubes"]) == 2
        assert exported["cubes"][0]["name"] == "orders"

    def test_ecommerce_roundtrip(self, converter):
        original = load("ecommerce.yaml")
        osi = converter.to_osi(original)
        exported = converter.from_osi(osi)

        names = {c["name"] for c in exported["cubes"]}
        assert names == {"orders", "customers", "products"}

    def test_advanced_roundtrip(self, converter):
        original = load("advanced.yaml")
        osi = converter.to_osi(original)
        exported = converter.from_osi(osi)

        assert "cubes" in exported
        assert len(exported["cubes"]) == 1
        measures = exported["cubes"][0].get("measures", [])
        measure_names = {m["name"] for m in measures}
        assert measure_names == {
            "total", "order_count", "revenue_ratio",
            "count_distinct_customers", "revenue_running_total", "double_total",
        }

    def test_roundtrip_creates_valid_osi(self, converter):
        original = load("orders.yaml")
        osi = converter.to_osi(original)
        assert "version" in osi
        assert "semantic_model" in osi
        assert len(osi["semantic_model"][0]["datasets"]) > 0
        assert len(osi["semantic_model"][0]["metrics"]) > 0
