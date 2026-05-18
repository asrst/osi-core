from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from ..base import BaseConverter


class DbtMetricFlowExporter(BaseConverter):
    VENDOR_NAME = "DBT_METRICFLOW"

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Use DbtMetricFlowImporter for MetricFlow -> OSI")

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._convert_from_osi(osi_model)

    def _convert_from_osi(self, osi: dict) -> dict:
        result: dict[str, Any] = {
            "semantic_models": [],
            "metrics": [],
        }

        model_map: dict[str, dict] = {}

        for sm_data in osi.get("semantic_model", []):
            for ds in sm_data.get("datasets", []):
                mf_model = self._export_semantic_model(ds)
                model_map[mf_model["name"]] = mf_model
                result["semantic_models"].append(mf_model)

            for rel in sm_data.get("relationships", []):
                self._inject_entity_from_relationship(rel, result["semantic_models"])

            for metric in sm_data.get("metrics", []):
                mf_entry = self._export_metric_or_measure(metric, model_map)
                if mf_entry:
                    result["metrics"].append(mf_entry)

        if not result["metrics"]:
            del result["metrics"]

        return result

    def _export_semantic_model(self, ds: dict) -> dict:
        mf: dict[str, Any] = {
            "name": ds["name"],
            "model": f"ref('{ds.get('source', 'unknown')}')",
            "entities": [],
            "dimensions": [],
        }

        pk = ds.get("primary_key", [])
        if pk:
            mf["entities"].append({
                "name": ds["name"],
                "type": "primary",
                "expr": pk[0],
            })

        defaults = self._get_extension_data(ds, "defaults")
        if defaults:
            mf["defaults"] = defaults

        for field in ds.get("fields", []):
            dim = field.get("dimension")
            if dim is not None:
                mf["dimensions"].append(self._export_dimension(field))
            else:
                measure = self._export_field_as_measure(field)
                if measure:
                    mf.setdefault("measures", []).append(measure)

        return mf

    def _export_dimension(self, field: dict) -> dict:
        dim: dict[str, Any] = {
            "name": field["name"],
            "type": "time" if field.get("dimension", {}).get("is_time") else "categorical",
        }

        expr = self._extract_expr(field.get("expression", {}), field["name"])
        if expr != field["name"]:
            dim["expr"] = expr

        granularity = self._get_extension_data(field, "time_granularity")
        if granularity:
            dim["type_params"] = {"time_granularity": granularity}

        return dim

    def _export_field_as_measure(self, field: dict) -> Optional[dict]:
        expr_str = self._extract_expr(field.get("expression", {}), field["name"])
        agg = self._detect_agg(expr_str)
        if agg:
            sql_expr = re.sub(r"^(SUM|COUNT|AVG|MIN|MAX|APPROX_PERCENTILE)\s*\(\s*(.*?)\s*\)\s*$", r"\2", expr_str, flags=re.IGNORECASE)
            return {
                "name": field["name"],
                "agg": agg.lower(),
                "expr": sql_expr or "*",
            }
        return None

    def _export_metric_or_measure(self, metric: dict, model_map: dict[str, dict]) -> Optional[dict]:
        meta = self._get_metric_meta(metric)
        kind = meta.get("kind") if meta else None

        if kind == "measure":
            source_model = meta.get("measure_source", "")
            target = model_map.get(source_model)
            if target:
                target.setdefault("measures", [])
                target["measures"].append(self._export_measure(metric, meta))
            return None

        if kind == "metric":
            return self._export_metric(metric, meta)

        expr = metric.get("expression", {})
        expr_str = self._extract_expr(expr, metric["name"])
        agg = self._detect_agg(expr_str)

        if agg:
            return None

        return self._export_metric(metric, {})

    @staticmethod
    def _export_measure(metric: dict, meta: dict) -> dict:
        expr_str = DbtMetricFlowExporter._extract_expr(metric.get("expression", {}), metric["name"])
        agg = meta.get("agg", "sum")
        m = re.match(r"^(SUM|COUNT|AVG|MIN|MAX|APPROX_PERCENTILE)\s*\(\s*(.*?)\s*\)\s*$", expr_str, re.IGNORECASE)
        sql_expr = m.group(2) if m else expr_str
        result = {
            "name": metric["name"],
            "agg": agg,
        }
        if sql_expr and sql_expr != "*":
            result["expr"] = sql_expr
        return result

    def _export_metric(self, metric: dict, meta: dict) -> dict:
        mtype = meta.get("metric_type", "simple")
        expr_str = self._extract_expr(metric.get("expression", {}), metric["name"])
        result: dict[str, Any] = {
            "name": metric["name"],
            "type": mtype,
            "type_params": {},
        }

        if mtype == "simple":
            measure = meta.get("measure", expr_str if expr_str != metric["name"] else metric["name"])
            result["type_params"]["measure"] = measure

        elif mtype == "ratio":
            result["type_params"] = {
                "numerator": {"name": meta.get("numerator", "?")},
                "denominator": {"name": meta.get("denominator", "?")},
            }

        elif mtype == "derived":
            result["type_params"]["expr"] = expr_str

        elif mtype == "cumulative":
            result["type_params"]["measure"] = meta.get("measure", metric["name"])
            if meta.get("window"):
                result["type_params"]["window"] = meta["window"]
            if meta.get("grain_to_date"):
                result["type_params"]["grain_to_date"] = meta["grain_to_date"]

        if metric.get("description"):
            desc = metric["description"]
            if desc.startswith("filter: "):
                result["filter"] = desc[8:]

        return result

    @staticmethod
    def _inject_entity_from_relationship(rel: dict, models: list[dict]):
        from_name = rel.get("from", "")
        to_name = rel.get("to", "")
        from_cols = rel.get("from_columns", [])

        for m in models:
            if m["name"] == from_name:
                entity_names = {e["name"] for e in m.get("entities", [])}
                if to_name not in entity_names:
                    expr = from_cols[0] if from_cols else f"{to_name}_id"
                    m["entities"].append({
                        "name": to_name,
                        "type": "foreign",
                        "expr": expr,
                    })

    @staticmethod
    def _extract_expr(expression: dict, field_name: str) -> str:
        dialects = expression.get("dialects", [])
        for d in dialects:
            if d.get("dialect") == "ANSI_SQL":
                return d.get("expression", field_name)
        return field_name

    @staticmethod
    def _detect_agg(expr: str) -> Optional[str]:
        m = re.match(r"^(SUM|COUNT|AVG|MIN|MAX|APPROX_PERCENTILE)\s*\(", expr, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return None

    @staticmethod
    def _get_extension_data(obj: dict, key: str) -> Any:
        exts = obj.get("custom_extensions", [])
        for ext in exts:
            if ext.get("vendor_name") == "DBT_METRICFLOW":
                try:
                    data = json.loads(ext["data"])
                    if key in data:
                        return data[key]
                    for v in data.values():
                        if isinstance(v, dict) and key in v:
                            return v[key]
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
        return None

    @staticmethod
    def _get_metric_meta(metric: dict) -> Optional[dict]:
        exts = metric.get("custom_extensions", [])
        for ext in exts:
            if ext.get("vendor_name") == "DBT_METRICFLOW":
                try:
                    return json.loads(ext["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return None
