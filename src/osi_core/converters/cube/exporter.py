from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from ..base import BaseConverter


class CubeExporter(BaseConverter):
    VENDOR_NAME = "CUBE"

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Use CubeImporter for Cube -> OSI")

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._convert_from_osi(osi_model)

    def _convert_from_osi(self, osi: dict) -> dict:
        result: dict[str, Any] = {
            "cubes": [],
        }

        for sm_data in osi.get("semantic_model", []):
            cube_map: dict[str, list[dict]] = {}
            for ds in sm_data.get("datasets", []):
                cube = self._export_cube(ds)
                cube_map[ds["name"]] = cube.get("measures", [])
                result["cubes"].append(cube)

            for rel in sm_data.get("relationships", []):
                self._inject_join_from_relationship(rel, result["cubes"])

            for metric in sm_data.get("metrics", []):
                meta = self._get_metric_meta(metric)
                if not meta:
                    continue
                cube_name = meta.get("cube_name", "")
                measure = self._export_measure_from_metric(metric, meta)
                if measure:
                    for cube in result["cubes"]:
                        if cube["name"] == cube_name:
                            cube.setdefault("measures", []).append(measure)
                            break

        return result

    def _export_cube(self, ds: dict) -> dict:
        cube: dict[str, Any] = {
            "name": ds["name"],
        }

        source = ds.get("source", "")
        is_subquery = self._get_extension_data(ds, "is_subquery")
        if is_subquery:
            cube["sql"] = source
        else:
            cube["sql_table"] = source

        for ext in ds.get("custom_extensions", []):
            if ext.get("vendor_name") == "CUBE":
                try:
                    data = json.loads(ext["data"])
                    if data.get("is_subquery"):
                        pass
                except (json.JSONDecodeError, TypeError):
                    pass

        pk_list = ds.get("primary_key", [])
        pk_column = pk_list[0] if pk_list else None

        dims: list[dict] = []
        for field in ds.get("fields", []):
            dim = field.get("dimension")
            if dim is not None:
                dims.append(self._export_dimension(field, is_pk=(field["name"] == pk_column)))
        if dims:
            cube["dimensions"] = dims

        return cube

    def _export_dimension(self, field: dict, is_pk: bool = False) -> dict:
        dim: dict[str, Any] = {
            "name": field["name"],
        }

        expr = self._extract_expr(field.get("expression", {}), field["name"])
        if expr:
            dim["sql"] = f"${{CUBE}}.{expr}"
        else:
            dim["sql"] = f"${{CUBE}}.{field['name']}"

        is_time = field.get("dimension", {}).get("is_time", False)
        if is_time:
            dim["type"] = "time"
        else:
            original_type = self._get_extension_data(field, "original_type")
            dim["type"] = original_type or "string"

        if is_pk:
            dim["primary_key"] = True

        return dim

    @staticmethod
    def _inject_join_from_relationship(rel: dict, cubes: list[dict]):
        from_name = rel.get("from", "")
        to_name = rel.get("to", "")
        from_cols = rel.get("from_columns", [])
        to_cols = rel.get("to_columns", [])

        for cube in cubes:
            if cube["name"] == from_name:
                from_col = from_cols[0] if from_cols else "id"
                to_col = to_cols[0] if to_cols else "id"
                join_sql = f"${{CUBE}}.{from_col} = ${{{to_name}}}.{to_col}"
                cube.setdefault("joins", []).append({
                    "name": to_name,
                    "sql": join_sql,
                    "relationship": "many_to_one",
                })

    def _export_measure_from_metric(self, metric: dict, meta: dict) -> Optional[dict]:
        mtype = meta.get("type", "sum")
        expr_str = self._extract_expr(metric.get("expression", {}), metric["name"])
        original_name = meta.get("original_name", metric["name"])

        measure: dict[str, Any] = {
            "name": original_name,
            "type": mtype,
        }

        if mtype == "count":
            if expr_str != "COUNT(*)":
                sql_expr = self._strip_aggregate(expr_str)
                measure["sql"] = sql_expr if sql_expr else ""
        elif mtype == "number":
            measure["sql"] = expr_str
        else:
            sql_expr = self._strip_aggregate(expr_str)
            if sql_expr:
                measure["sql"] = sql_expr

        if measure.get("sql") == "" or measure.get("sql") == "*":
            del measure["sql"]

        return measure

    @staticmethod
    def _strip_aggregate(expr: str) -> str:
        m = re.match(r"^(SUM|COUNT|AVG|MIN|MAX|APPROX_PERCENTILE)\s*\(\s*(.*?)\s*\)\s*$", expr, re.IGNORECASE)
        if m:
            inner = m.group(2)
            if inner == "DISTINCT *":
                inner = "*"
            if inner.startswith("DISTINCT "):
                inner = inner[9:]
            return inner
        if re.match(r"^COUNT\s*\(\s*DISTINCT\s+", expr, re.IGNORECASE):
            inner = re.sub(r"^COUNT\s*\(\s*DISTINCT\s+(.*?)\s*\)\s*$", r"\1", expr, flags=re.IGNORECASE)
            if inner:
                return inner
        return expr

    @staticmethod
    def _extract_expr(expression: dict, field_name: str) -> str:
        dialects = expression.get("dialects", [])
        for d in dialects:
            if d.get("dialect") == "ANSI_SQL":
                return d.get("expression", field_name)
        return field_name

    @staticmethod
    def _get_extension_data(obj: dict, key: str) -> Any:
        exts = obj.get("custom_extensions", [])
        for ext in exts:
            if ext.get("vendor_name") == "CUBE":
                try:
                    data = json.loads(ext["data"])
                    if key in data:
                        return data[key]
                except (json.JSONDecodeError, TypeError):
                    pass
        return None

    @staticmethod
    def _get_metric_meta(metric: dict) -> Optional[dict]:
        exts = metric.get("custom_extensions", [])
        for ext in exts:
            if ext.get("vendor_name") == "CUBE":
                try:
                    return json.loads(ext["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return None
