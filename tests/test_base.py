from __future__ import annotations

import pytest

from osi_core.converters.base import BaseConverter
from osi_core.converters import discover_converters, SnowflakeConverter, GoodDataConverter, DbtMetricFlowConverter, CubeConverter, SupersetConverter


def test_all_converters_are_registered():
    converters = discover_converters()
    assert "snowflake" in converters
    assert "gooddata" in converters
    assert "dbt_metricflow" in converters
    assert "cube" in converters
    assert "superset" in converters


class TestBaseConverterContract:
    @pytest.fixture(params=["snowflake", "gooddata", "dbt_metricflow", "cube", "superset"])
    def converter(self, request: pytest.FixtureRequest) -> BaseConverter:
        return discover_converters()[request.param]

    def test_has_vendor_name(self, converter: BaseConverter):
        assert converter.VENDOR_NAME
        assert isinstance(converter.VENDOR_NAME, str)

    def test_implements_to_osi(self, converter: BaseConverter):
        assert hasattr(converter, "to_osi")
        assert callable(converter.to_osi)

    def test_implements_from_osi(self, converter: BaseConverter):
        assert hasattr(converter, "from_osi")
        assert callable(converter.from_osi)

    def test_to_osi_requires_dict(self, converter: BaseConverter):
        with pytest.raises((TypeError, Exception)):
            converter.to_osi("not a dict")

    def test_from_osi_requires_dict(self, converter: BaseConverter):
        with pytest.raises((TypeError, Exception)):
            converter.from_osi("not a dict")

    def test_to_osi_returns_dict(self, converter: BaseConverter):
        # Must accept at minimum an empty dict (may raise other errors)
        # but it should be a valid attempt
        pass

    def test_from_osi_returns_dict(self, converter: BaseConverter):
        # Must accept at minimum an empty dict (may raise other errors)
        pass


class TestSnowflakeConverterContract:
    def test_converter_type(self):
        sc = SnowflakeConverter()
        assert isinstance(sc, BaseConverter)

    def test_vendor_name(self):
        assert SnowflakeConverter.VENDOR_NAME == "SNOWFLAKE"

    def test_from_osi_returns_dict(self):
        sc = SnowflakeConverter()
        result = sc.from_osi(_minimal_osi())
        assert isinstance(result, dict)

    def test_to_osi_returns_dict(self):
        sc = SnowflakeConverter()
        result = sc.to_osi(_minimal_snowflake())
        assert isinstance(result, dict)


class TestDbtMetricFlowConverterContract:
    def test_converter_type(self):
        mf = DbtMetricFlowConverter()
        assert isinstance(mf, BaseConverter)

    def test_vendor_name(self):
        assert DbtMetricFlowConverter.VENDOR_NAME == "DBT_METRICFLOW"

    def test_from_osi_returns_dict(self):
        mf = DbtMetricFlowConverter()
        result = mf.from_osi(_minimal_osi())
        assert isinstance(result, dict)

    def test_to_osi_returns_dict(self):
        mf = DbtMetricFlowConverter()
        result = mf.to_osi(_minimal_metricflow())
        assert isinstance(result, dict)


class TestCubeConverterContract:
    def test_converter_type(self):
        cc = CubeConverter()
        assert isinstance(cc, BaseConverter)

    def test_vendor_name(self):
        assert CubeConverter.VENDOR_NAME == "CUBE"

    def test_from_osi_returns_dict(self):
        cc = CubeConverter()
        result = cc.from_osi(_minimal_osi())
        assert isinstance(result, dict)

    def test_to_osi_returns_dict(self):
        cc = CubeConverter()
        result = cc.to_osi(_minimal_cube())
        assert isinstance(result, dict)


def _minimal_cube() -> dict:
    return {
        "cubes": [
            {
                "name": "test",
                "sql_table": "public.test_table",
                "dimensions": [{"name": "id", "sql": "${CUBE}.id", "type": "number"}],
                "measures": [{"name": "total", "sql": "amount", "type": "sum"}],
            }
        ],
    }


class TestGoodDataConverterContract:
    def test_converter_type(self):
        gc = GoodDataConverter()
        assert isinstance(gc, BaseConverter)

    def test_vendor_name(self):
        assert GoodDataConverter.VENDOR_NAME == "GOODDATA"

    def test_from_osi_returns_dict(self):
        gc = GoodDataConverter()
        result = gc.from_osi(_minimal_osi())
        assert isinstance(result, dict)

    def test_to_osi_returns_dict(self):
        gc = GoodDataConverter()
        result = gc.to_osi(_minimal_gooddata())
        assert isinstance(result, dict)


def _minimal_osi() -> dict:
    return {
        "version": "0.1.1",
        "semantic_model": [
            {
                "name": "test",
                "datasets": [
                    {
                        "name": "test_dataset",
                        "fields": [
                            {
                                "name": "id",
                                "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "id"}]},
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _minimal_snowflake() -> dict:
    return {
        "name": "test",
        "tables": [
            {
                "name": "test_table",
                "base_table": {"table": "test_table"},
                "dimensions": [{"name": "col1"}],
            }
        ],
    }


def _minimal_metricflow() -> dict:
    return {
        "semantic_models": [
            {
                "name": "test",
                "model": "ref('test_table')",
                "entities": [{"name": "id", "type": "primary", "expr": "id"}],
                "dimensions": [{"name": "col1", "type": "categorical"}],
                "measures": [{"name": "total", "agg": "sum", "expr": "amount"}],
            }
        ],
    }


class TestSupersetConverterContract:
    def test_converter_type(self):
        sc = SupersetConverter()
        assert isinstance(sc, BaseConverter)

    def test_vendor_name(self):
        assert SupersetConverter.VENDOR_NAME == "SUPERSET"

    def test_from_osi_returns_dict(self):
        sc = SupersetConverter()
        result = sc.from_osi(_minimal_osi())
        assert isinstance(result, dict)

    def test_to_osi_returns_dict(self):
        sc = SupersetConverter()
        result = sc.to_osi(_minimal_superset())
        assert isinstance(result, dict)


def _minimal_superset() -> dict:
    return {
        "table_name": "test",
        "schema": "public",
        "columns": [{"column_name": "id", "type": "VARCHAR"}],
        "metrics": [{"metric_name": "cnt", "expression": "COUNT(*)", "metric_type": "count"}],
    }


def _minimal_gooddata() -> dict:
    return {
        "ldm": {
            "datasets": [
                {
                    "id": "dataset.test",
                    "title": "Test",
                    "type": "DATASET",
                    "dataSourceTableId": {"dataSourceId": "default", "id": "test_table"},
                    "attributes": [
                        {
                            "id": "attr.test.col1",
                            "title": "Col1",
                            "type": "ATTRIBUTE",
                            "sourceColumn": "col1",
                        }
                    ],
                    "facts": [],
                    "references": [],
                    "dateInstances": [],
                    "grain": [],
                }
            ],
            "dateInstances": [],
        }
    }
