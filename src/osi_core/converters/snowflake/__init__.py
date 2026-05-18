from .exporter import SnowflakeExporter
from .importer import SnowflakeImporter

from ..base import BaseConverter
from typing import Any, Dict


class SnowflakeConverter(BaseConverter):
    """Combined Snowflake converter with both import and export."""
    VENDOR_NAME = "SNOWFLAKE"

    def __init__(self):
        self._exporter = SnowflakeExporter()
        self._importer = SnowflakeImporter()

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._importer.to_osi(native_model, **kwargs)

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._exporter.from_osi(osi_model, **kwargs)


__all__ = ["SnowflakeConverter", "SnowflakeExporter", "SnowflakeImporter"]
