from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from ..base import BaseConverter


_CUBE_MEASURE_TO_SQL: dict[str, str] = {
    "count": "COUNT({expr})",
    "count_distinct": "COUNT(DISTINCT {expr})",
    "sum": "SUM({expr})",
    "avg": "AVG({expr})",
    "min": "MIN({expr})",
    "max": "MAX({expr})",
}


class CubeImporter(BaseConverter):
    VENDOR_NAME = "CUBE"

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._convert_to_osi(native_model, **kwargs)

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Use CubeExporter for OSI -> Cube")

    def _convert_to_osi(self, cube_data: dict, **kwargs) -> dict:
        result = {
            "version": "0.1.1",
            "semantic_model": [{
                "name": kwargs.get("model_name", "cube_model"),
                "datasets": [],
                "relationships": [],
                "metrics": [],
            }],
        }

        sm = result["semantic_model"][0]
        cube_map: dict[str, dict] = {}

        for cube in cube_data.get("cubes", []):
            dataset = self._convert_cube(cube)
            cube_map[dataset["name"]] = dataset
            sm["datasets"].append(dataset)

            for measure in cube.get("measures", []):
                metric = self._convert_measure(measure, cube["name"])
                sm["metrics"].append(metric)

        for cube in cube_data.get("cubes", []):
            for join in cube.get("joins", []):
                rel = self._build_relationship(cube["name"], join, cube_map)
                if rel:
                    sm["relationships"].append(rel)

        return result

    @staticmethod
    def _extract_expression(sql_str: str) -> str:
        if not sql_str:
            return ""
        return re.sub(r"\$\{CUBE\}\.", "", sql_str)

    @staticmethod
    def _extract_join_columns(sql_str: str) -> Optional[tuple[list[str], list[str]]]:
        m = re.match(r"\$\{CUBE\}\.(\w+)\s*=\s*\$\{(\w+)\}\.(\w+)", sql_str.strip())
        if m:
            return [m.group(1)], [m.group(3)]
        m = re.match(r"\$\{(\w+)\}\.(\w+)\s*=\s*\$\{CUBE\}\.(\w+)", sql_str.strip())
        if m:
            return [m.group(3)], [m.group(2)]
        return None

    def _convert_cube(self, cube: dict) -> dict:
        dataset: dict[str, Any] = {
            "name": cube["name"],
            "fields": [],
        }

        sql_table = cube.get("sql_table")
        custom_sql = cube.get("sql")
        if sql_table:
            dataset["source"] = sql_table
        elif custom_sql:
            dataset["source"] = custom_sql
            dataset.setdefault("custom_extensions", []).append(
                {"vendor_name": "CUBE", "data": json.dumps({"is_subquery": True})}
            )
        else:
            dataset["source"] = cube["name"]

        cube_pk = cube.get("primary_key")
        dim_pk = None

        for dim in cube.get("dimensions", []):
            is_pk = dim.get("primary_key", False)
            if is_pk:
                dim_pk = dim["name"]
            elif cube_pk and dim["name"] == cube_pk:
                is_pk = True
                dim_pk = dim["name"]
            field = self._convert_dimension(dim, is_pk)
            dataset["fields"].append(field)

        if not dim_pk and cube_pk:
            dim_pk = cube_pk

        if dim_pk:
            dataset["primary_key"] = [dim_pk]

        return dataset

    def _convert_dimension(self, dim: dict, is_pk: bool = False) -> dict:
        raw_expr = self._extract_expression(dim.get("sql", ""))
        field: dict[str, Any] = {
            "name": dim["name"],
            "expression": {
                "dialects": [{
                    "dialect": "ANSI_SQL",
                    "expression": raw_expr or dim["name"],
                }],
            },
        }

        cube_type = dim.get("type", "string")
        is_time = cube_type == "time"
        field["dimension"] = {"is_time": is_time}

        ext_data: dict[str, Any] = {}
        if not is_time and cube_type not in ("string",):
            ext_data["original_type"] = cube_type
        if is_pk:
            ext_data["primary_key"] = True
        if ext_data:
            field["custom_extensions"] = [
                {"vendor_name": "CUBE", "data": json.dumps(ext_data)}
            ]

        return field

    def _convert_measure(self, measure: dict, cube_name: str) -> dict:
        mtype = measure.get("type", "sum")
        raw_sql = measure.get("sql", "")
        sql_expr = self._extract_expression(raw_sql) if raw_sql else None

        if mtype == "count" and not sql_expr:
            sql = "COUNT(*)"
        elif mtype == "number":
            sql = sql_expr or measure["name"]
        else:
            template = _CUBE_MEASURE_TO_SQL.get(mtype)
            if template:
                sql = template.format(expr=sql_expr or "*")
            else:
                sql = f"{mtype.upper()}({sql_expr or '*'})"

        metric: dict[str, Any] = {
            "name": f"{cube_name}__{measure['name']}",
            "expression": {
                "dialects": [{
                    "dialect": "ANSI_SQL",
                    "expression": sql,
                }],
            },
            "custom_extensions": [
                {
                    "vendor_name": "CUBE",
                    "data": json.dumps({
                        "cube_name": cube_name,
                        "original_name": measure["name"],
                        "type": mtype,
                    }),
                }
            ],
        }

        if measure.get("description"):
            metric["description"] = measure["description"]

        return metric

    @staticmethod
    def _find_cube_by_name(name: str, cube_map: dict) -> Optional[str]:
        if name in cube_map:
            return name
        for key in cube_map:
            if key.lower() == name.lower():
                return key
        return None

    def _build_relationship(self, from_name: str, join: dict, cube_map: dict) -> Optional[dict]:
        to_name = join["name"]
        sql_str = join.get("sql", "")

        columns = self._extract_join_columns(sql_str)
        if not columns:
            return None

        from_cols, to_cols = columns
        resolved_to = self._find_cube_by_name(to_name, cube_map)
        if not resolved_to:
            return None

        return {
            "name": f"{from_name}_to_{resolved_to}",
            "from": from_name,
            "to": resolved_to,
            "from_columns": from_cols,
            "to_columns": to_cols,
        }
