from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from ..base import BaseConverter


class SupersetExporter(BaseConverter):
    VENDOR_NAME = "SUPERSET"

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Use SupersetImporter for Superset -> OSI")

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._convert_from_osi(osi_model)

    def _convert_from_osi(self, osi: dict) -> dict:
        for sm_data in osi.get("semantic_model", []):
            for ds in sm_data.get("datasets", []):
                return self._export_dataset(ds, sm_data.get("metrics", []))

        return {
            "table_name": "unknown",
            "version": "1.0.0",
            "columns": [],
        }

    def _export_dataset(self, ds: dict, all_metrics: list[dict]) -> dict:
        source = ds.get("source", "")
        table_name, schema, is_subquery = self._parse_source(source, ds)

        result: dict[str, Any] = {
            "table_name": table_name,
            "version": "1.0.0",
            "columns": [],
        }

        if schema:
            result["schema"] = schema
        if is_subquery:
            result["sql"] = source
        else:
            result["sql"] = None

        ext_data = self._get_extension_data(ds)
        main_dttm = ext_data.get("main_dttm_col") if ext_data else None

        if main_dttm:
            result["main_dttm_col"] = main_dttm

        if ds.get("description"):
            result["description"] = ds["description"]

        columns = []
        pk_list = ds.get("primary_key", [])
        pk_col = pk_list[0] if pk_list else None

        for field in ds.get("fields", []):
            col = self._export_column(field, main_dttm, pk_col)
            columns.append(col)
        if columns:
            result["columns"] = columns

        metrics = []
        for metric in all_metrics:
            m = self._export_metric(metric)
            if m:
                metrics.append(m)
        if metrics:
            result["metrics"] = metrics

        if ext_data:
            extra_json = ext_data.get("extra")
            if extra_json and isinstance(extra_json, dict):
                result["extra"] = json.dumps(extra_json)
            uuid_val = ext_data.get("uuid")
            if uuid_val:
                result["uuid"] = uuid_val

        return result

    @staticmethod
    def _parse_source(source: str, ds: dict) -> tuple[str, Optional[str], bool]:
        ext_data = None
        for ext in ds.get("custom_extensions", []):
            if ext.get("vendor_name") == "SUPERSET":
                try:
                    ext_data = json.loads(ext["data"])
                except (json.JSONDecodeError, TypeError):
                    pass

        is_subquery = False
        if ext_data and ext_data.get("is_subquery"):
            is_subquery = True

        if is_subquery:
            table_name = ds.get("name", "unknown")
            return table_name, None, True

        if "." in source:
            parts = source.split(".", 1)
            return parts[1], parts[0], False

        return source, None, False

    def _export_column(self, field: dict, main_dttm: Optional[str], pk_col: Optional[str]) -> dict:
        col: dict[str, Any] = {
            "column_name": field["name"],
        }

        if field.get("label"):
            col["verbose_name"] = field["label"]

        if field.get("description"):
            col["description"] = field["description"]

        expr = self._extract_expr(field.get("expression", {}), field["name"])
        has_custom_expr = expr and expr != field["name"]
        if has_custom_expr:
            col["expression"] = expr
        else:
            col["expression"] = None

        dim = field.get("dimension")
        is_dttm = dim is not None and dim.get("is_time", False)

        if is_dttm:
            col["is_dttm"] = True
            col["type"] = "TIMESTAMP WITHOUT TIME ZONE"
        elif dim is None:
            col["is_dttm"] = False
            if any(t in (expr or "").upper() for t in ("COUNT", "SUM", "AVG", "MIN", "MAX")):
                col["type"] = "DOUBLE PRECISION"
            else:
                col["type"] = "NUMERIC"
        else:
            col["is_dttm"] = False
            raw_type = self._get_extension_data(field, "original_type")
            if raw_type:
                col["type"] = raw_type
            else:
                col["type"] = "VARCHAR"

        col["groupby"] = dim is not None
        col["filterable"] = True
        col["is_active"] = True

        return col

    def _export_metric(self, metric: dict) -> Optional[dict]:
        metric_name = metric.get("name")
        if not metric_name:
            return None

        result: dict[str, Any] = {
            "metric_name": metric_name,
        }

        expr = self._extract_expr(metric.get("expression", {}), metric_name)
        result["expression"] = expr

        meta = self._get_metric_meta(metric)
        if meta:
            if "metric_type" in meta:
                result["metric_type"] = meta["metric_type"]
            else:
                result["metric_type"] = self._detect_metric_type(expr)
            if "verbose_name" in meta:
                result["verbose_name"] = meta["verbose_name"]
            if "d3format" in meta:
                result["d3format"] = meta["d3format"]
            if "warning_text" in meta:
                result["warning_text"] = meta["warning_text"]
        else:
            result["metric_type"] = self._detect_metric_type(expr)
            result["verbose_name"] = metric_name

        if not result.get("verbose_name"):
            result["verbose_name"] = metric_name

        if metric.get("description"):
            result["description"] = metric["description"]

        return result

    @staticmethod
    def _detect_metric_type(expr: str) -> Optional[str]:
        if not expr:
            return None
        upper = expr.upper().strip()
        if upper == "COUNT(*)":
            return "count"
        m = re.match(r"^(SUM|COUNT|AVG|MIN|MAX)\s*\(", upper)
        if m:
            func = m.group(1).lower()
            return func
        if "COUNT(DISTINCT" in upper:
            return "count_distinct"
        return None

    @staticmethod
    def _extract_expr(expression: dict, field_name: str) -> str:
        dialects = expression.get("dialects", [])
        for d in dialects:
            if d.get("dialect") == "ANSI_SQL":
                return d.get("expression", field_name)
        return field_name

    @staticmethod
    def _get_extension_data(obj: dict, key: Optional[str] = None) -> Any:
        exts = obj.get("custom_extensions", [])
        for ext in exts:
            if ext.get("vendor_name") == "SUPERSET":
                try:
                    data = json.loads(ext["data"])
                    if key is not None:
                        return data.get(key)
                    return data
                except (json.JSONDecodeError, TypeError):
                    pass
        return None if key else {}

    @staticmethod
    def _get_metric_meta(metric: dict) -> Optional[dict]:
        exts = metric.get("custom_extensions", [])
        for ext in exts:
            if ext.get("vendor_name") == "SUPERSET":
                try:
                    return json.loads(ext["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return None
