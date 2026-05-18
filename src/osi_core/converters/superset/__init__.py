from .exporter import SupersetExporter
from .importer import SupersetImporter

from ..base import BaseConverter
from typing import Any, Dict


class SupersetConverter(BaseConverter):
    VENDOR_NAME = "SUPERSET"

    def __init__(self):
        self._importer = SupersetImporter()
        self._exporter = SupersetExporter()

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._importer.to_osi(native_model, **kwargs)

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._exporter.from_osi(osi_model, **kwargs)


__all__ = ["SupersetConverter", "SupersetImporter", "SupersetExporter"]
