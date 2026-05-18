from .base import BaseConverter

_CONVERTERS: dict[str, BaseConverter] = {}


def register_converter(name: str, converter: BaseConverter) -> None:
    _CONVERTERS[name] = converter


def discover_converters() -> dict[str, BaseConverter]:
    return dict(_CONVERTERS)


__all__ = ["BaseConverter", "register_converter", "discover_converters"]
