from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from ..base import BaseConverter


_NUMERIC_TYPES = frozenset({
    "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT",
    "DECIMAL", "NUMERIC",
    "FLOAT", "DOUBLE", "DOUBLE PRECISION", "REAL",
})


class SupersetImporter(BaseConverter):
    VENDOR_NAME = "SUPERSET"

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._convert_to_osi(native_model, **kwargs)

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Use SupersetExporter for OSI -> Superset")

    def _convert_to_osi(self, dataset: dict, **kwargs) -> dict:
        table_name = dataset.get("table_name", "unknown")
        schema = dataset.get("schema") or ""
        sql = dataset.get("sql")

        if sql:
            source = sql
            subquery_ext = True
        elif schema:
            source = f"{schema}.{table_name}"
            subquery_ext = False
        else:
            source = table_name
            subquery_ext = False

        ds: dict[str, Any] = {
            "name": table_name,
            "source": source,
            "fields": [],
        }

        if subquery_ext:
            ds["custom_extensions"] = [
                {"vendor_name": "SUPERSET", "data": json.dumps({"is_subquery": True})}
            ]

        main_dttm = dataset.get("main_dttm_col")

        ext_data: dict[str, Any] = {}
        if main_dttm:
            ext_data["main_dttm_col"] = main_dttm

        extra_str = dataset.get("extra")
        if extra_str and isinstance(extra_str, str) and extra_str.strip():
            try:
                extra_data = json.loads(extra_str)
                if extra_data:
                    ext_data["extra"] = extra_data
            except json.JSONDecodeError:
                pass

        if dataset.get("uuid"):
            ext_data["uuid"] = dataset["uuid"]

        if ext_data:
            ds.setdefault("custom_extensions", []).append(
                {"vendor_name": "SUPERSET", "data": json.dumps(ext_data)}
            )

        pk_candidate = None
        for col in dataset.get("columns", []):
            col_name = col.get("column_name", "")
            if col_name == "id":
                pk_candidate = col_name
                break
            if col_name.endswith("_id") and pk_candidate is None:
                pk_candidate = col_name

        for col in dataset.get("columns", []):
            field = self._convert_column(col, main_dttm)
            ds["fields"].append(field)

        if pk_candidate:
            ds["primary_key"] = [pk_candidate]
        elif ds["fields"]:
            ds["primary_key"] = [ds["fields"][0]["name"]]

        result = {
            "version": "0.1.1",
            "semantic_model": [{
                "name": kwargs.get("model_name", table_name),
                "datasets": [ds],
                "metrics": [],
            }],
        }

        sm = result["semantic_model"][0]
        for metric_def in dataset.get("metrics", []):
            metric = self._convert_metric(metric_def)
            if metric:
                sm["metrics"].append(metric)

        return result

    def _convert_column(self, col: dict, main_dttm: Optional[str]) -> dict:
        col_name = col.get("column_name", "unknown")
        field: dict[str, Any] = {
            "name": col_name,
            "expression": {
                "dialects": [{
                    "dialect": "ANSI_SQL",
                    "expression": col.get("expression") or col_name,
                }],
            },
        }

        raw_type = (col.get("type") or "").upper().strip()
        is_dttm = col.get("is_dttm", False) or col_name == main_dttm
        has_expression = bool(col.get("expression"))

        is_numeric = any(raw_type.startswith(t) for t in _NUMERIC_TYPES)

        if is_dttm:
            field["dimension"] = {"is_time": True}
        elif is_numeric and not has_expression:
            pass
        else:
            field["dimension"] = {"is_time": False}

        if col.get("verbose_name"):
            field["label"] = col["verbose_name"]

        if col.get("description"):
            field["description"] = col["description"]

        if not has_expression and col.get("expression") is None:
            pass

        return field

    def _convert_metric(self, metric_def: dict) -> Optional[dict]:
        metric_name = metric_def.get("metric_name")
        if not metric_name:
            return None

        expression = metric_def.get("expression", "")
        if not expression:
            return None

        metric: dict[str, Any] = {
            "name": metric_name,
            "expression": {
                "dialects": [{
                    "dialect": "ANSI_SQL",
                    "expression": expression,
                }],
            },
        }

        if metric_def.get("description"):
            metric["description"] = metric_def["description"]

        ext_data: dict[str, Any] = {}
        metric_type = metric_def.get("metric_type")
        if metric_type is not None:
            ext_data["metric_type"] = metric_type
        if metric_def.get("verbose_name"):
            ext_data["verbose_name"] = metric_def["verbose_name"]
        if metric_def.get("d3format"):
            ext_data["d3format"] = metric_def["d3format"]
        if metric_def.get("warning_text"):
            ext_data["warning_text"] = metric_def["warning_text"]

        if ext_data:
            metric["custom_extensions"] = [
                {"vendor_name": "SUPERSET", "data": json.dumps(ext_data)}
            ]

        return metric
