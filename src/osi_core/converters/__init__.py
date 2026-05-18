from .base import BaseConverter
from .snowflake import SnowflakeConverter
from .gooddata import GoodDataConverter
from .metricflow import DbtMetricFlowConverter

_CONVERTERS: dict[str, BaseConverter] = {
    "snowflake": SnowflakeConverter(),
    "gooddata": GoodDataConverter(),
    "dbt_metricflow": DbtMetricFlowConverter(),
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
    "register_converter",
    "discover_converters",
]
