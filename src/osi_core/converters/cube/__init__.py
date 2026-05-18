from .exporter import CubeExporter
from .importer import CubeImporter

from ..base import BaseConverter
from typing import Any, Dict


class CubeConverter(BaseConverter):
    VENDOR_NAME = "CUBE"

    def __init__(self):
        self._importer = CubeImporter()
        self._exporter = CubeExporter()

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._importer.to_osi(native_model, **kwargs)

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._exporter.from_osi(osi_model, **kwargs)


__all__ = ["CubeConverter", "CubeImporter", "CubeExporter"]
