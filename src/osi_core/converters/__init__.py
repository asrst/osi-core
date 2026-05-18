from .base import BaseConverter
from .snowflake import SnowflakeConverter
from .gooddata import GoodDataConverter

_CONVERTERS: dict[str, BaseConverter] = {
    "snowflake": SnowflakeConverter(),
    "gooddata": GoodDataConverter(),
}


def register_converter(name: str, converter: BaseConverter) -> None:
    _CONVERTERS[name] = converter


def discover_converters() -> dict[str, BaseConverter]:
    return dict(_CONVERTERS)


__all__ = [
    "BaseConverter",
    "SnowflakeConverter",
    "GoodDataConverter",
    "register_converter",
    "discover_converters",
]
