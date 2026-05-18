from .base import BaseConverter
from .snowflake import SnowflakeConverter
from .gooddata import GoodDataConverter
from .metricflow import DbtMetricFlowConverter
from .cube import CubeConverter

_CONVERTERS: dict[str, BaseConverter] = {
    "snowflake": SnowflakeConverter(),
    "gooddata": GoodDataConverter(),
    "dbt_metricflow": DbtMetricFlowConverter(),
    "cube": CubeConverter(),
}


def register_converter(name: str, converter: BaseConverter) -> None:
    _CONVERTERS[name] = converter


def discover_converters() -> dict[str, BaseConverter]:
    return dict(_CONVERTERS)


__all__ = [
    "BaseConverter",
    "SnowflakeConverter",
    "GoodDataConverter",
    "DbtMetricFlowConverter",
    "CubeConverter",
    "register_converter",
    "discover_converters",
]
