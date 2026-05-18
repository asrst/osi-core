from .importer import GoodDataImporter
from .exporter import GoodDataExporter

from ..base import BaseConverter
from typing import Any, Dict


class GoodDataConverter(BaseConverter):
    """Combined GoodData converter with both import and export."""
    VENDOR_NAME = "GOODDATA"

    def __init__(self):
        self._importer = GoodDataImporter()
        self._exporter = GoodDataExporter()

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._importer.to_osi(native_model, **kwargs)

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._exporter.from_osi(osi_model, **kwargs)


__all__ = ["GoodDataConverter", "GoodDataImporter", "GoodDataExporter"]
