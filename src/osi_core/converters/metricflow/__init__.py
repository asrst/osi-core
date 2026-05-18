from .exporter import DbtMetricFlowExporter
from .importer import DbtMetricFlowImporter

from ..base import BaseConverter
from typing import Any, Dict


class DbtMetricFlowConverter(BaseConverter):
    VENDOR_NAME = "DBT_METRICFLOW"

    def __init__(self):
        self._importer = DbtMetricFlowImporter()
        self._exporter = DbtMetricFlowExporter()

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._importer.to_osi(native_model, **kwargs)

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._exporter.from_osi(osi_model, **kwargs)


__all__ = ["DbtMetricFlowConverter", "DbtMetricFlowImporter", "DbtMetricFlowExporter"]
