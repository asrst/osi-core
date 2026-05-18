from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from ..base import BaseConverter


_AGG_TO_SQL: dict[str, str] = {
    "count": "COUNT({expr})",
    "count_distinct": "COUNT(DISTINCT {expr})",
    "sum": "SUM({expr})",
    "avg": "AVG({expr})",
    "average": "AVG({expr})",
    "min": "MIN({expr})",
    "max": "MAX({expr})",
    "sum_boolean": "SUM(CAST({expr} AS INTEGER))",
    "median": "APPROX_PERCENTILE({expr}, 0.5)",
    "percentile": "APPROX_PERCENTILE({expr}, 0.5)",
}


class DbtMetricFlowImporter(BaseConverter):
    VENDOR_NAME = "DBT_METRICFLOW"

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._convert_to_osi(native_model, **kwargs)

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Use DbtMetricFlowExporter for OSI -> MetricFlow")

    def _convert_to_osi(self, mf: dict, **kwargs) -> dict:
        result = {
            "version": "0.1.1",
            "semantic_model": [{
                "name": kwargs.get("model_name", "metricflow_model"),
                "datasets": [],
                "relationships": [],
                "metrics": [],
            }],
        }

        sm = result["semantic_model"][0]
        model_map: dict[str, dict] = {}
        seen_metrics: set[str] = set()

        for mf_model in mf.get("semantic_models", []):
            dataset = self._convert_semantic_model(mf_model)
            model_map[dataset["name"]] = dataset
            sm["datasets"].append(dataset)

            for measure in mf_model.get("measures", []):
                metric = self._convert_measure(measure, mf_model["name"])
                if metric["name"] not in seen_metrics:
                    seen_metrics.add(metric["name"])
                    sm["metrics"].append(metric)

        for mf_model in mf.get("semantic_models", []):
            for entity in mf_model.get("entities", []):
                if entity.get("type") == "foreign":
                    rel = self._build_relationship(mf_model, entity, model_map)
                    if rel:
                        sm["relationships"].append(rel)

        for metric_def in mf.get("metrics", []):
            metric = self._convert_metric(metric_def, model_map)
            if metric and metric["name"] not in seen_metrics:
                seen_metrics.add(metric["name"])
                sm["metrics"].append(metric)

        return result

    @staticmethod
    def _extract_table_name(model_ref: Any) -> str:
        if not model_ref:
            return "unknown"
        m = re.match(r"""ref\(['"]([^'"]+)['"]\)""", str(model_ref))
        if m:
            return m.group(1)
        return str(model_ref)

    def _convert_semantic_model(self, mf_model: dict) -> dict:
        dataset: dict[str, Any] = {
            "name": mf_model["name"],
            "fields": [],
        }

        model_ref = mf_model.get("model", "")
        dataset["source"] = self._extract_table_name(model_ref)

        for entity in mf_model.get("entities", []):
            if entity.get("type") == "primary":
                dataset["primary_key"] = [entity.get("expr", entity["name"])]
                break

        if "primary_key" not in dataset:
            primary_entity = mf_model.get("primary_entity")
            if primary_entity:
                dataset["primary_key"] = [primary_entity]

        for dim in mf_model.get("dimensions", []):
            dataset["fields"].append(self._convert_dimension(dim))

        defaults = mf_model.get("defaults")
        if defaults and defaults.get("agg_time_dimension"):
            dataset["custom_extensions"] = [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": json.dumps({"defaults": defaults}),
                }
            ]

        return dataset

    def _convert_dimension(self, dim: dict) -> dict:
        field: dict[str, Any] = {
            "name": dim["name"],
            "expression": {
                "dialects": [{
                    "dialect": "ANSI_SQL",
                    "expression": dim.get("expr", dim["name"]),
                }],
            },
        }

        dim_type = dim.get("type", "categorical")
        field["dimension"] = {"is_time": dim_type == "time"}

        type_params = dim.get("type_params", {})
        if type_params.get("time_granularity"):
            field["custom_extensions"] = [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": json.dumps({"time_granularity": type_params["time_granularity"]}),
                }
            ]

        return field

    def _convert_measure(self, measure: dict, model_name: str) -> dict:
        agg = measure.get("agg", "sum")
        expr = measure.get("expr", "*")
        name = measure["name"]

        sql = self._build_agg_sql(agg, expr)

        metric: dict[str, Any] = {
            "name": name,
            "expression": {
                "dialects": [{
                    "dialect": "ANSI_SQL",
                    "expression": sql,
                }],
            },
            "custom_extensions": [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": json.dumps({
                        "kind": "measure",
                        "measure_source": model_name,
                        "agg": agg,
                    }),
                }
            ],
        }

        if measure.get("description"):
            metric["description"] = measure["description"]

        return metric

    @staticmethod
    def _build_agg_sql(agg: str, expr: str) -> str:
        template = _AGG_TO_SQL.get(agg)
        if template:
            if agg == "count" and (expr == "*" or expr is None):
                return "COUNT(*)"
            return template.format(expr=expr)
        return f"{agg.upper()}({expr})"

    @staticmethod
    def _resolve_entity_name(entity_name: str, model_map: dict) -> Optional[str]:
        if entity_name in model_map:
            return entity_name
        for candidate in (entity_name + "s", entity_name[:-1] if entity_name.endswith("s") else None):
            if candidate and candidate in model_map:
                return candidate
        for name in model_map:
            if name.lower() == entity_name.lower():
                return name
        return None

    def _build_relationship(self, mf_model: dict, entity: dict, model_map: dict) -> Optional[dict]:
        from_name = mf_model["name"]
        to_name = entity["name"]
        from_col = entity.get("expr", entity["name"])

        resolved_to = self._resolve_entity_name(to_name, model_map)
        if not resolved_to:
            return None

        to_pk = model_map[resolved_to].get("primary_key", ["id"])

        return {
            "name": f"{from_name}_to_{resolved_to}",
            "from": from_name,
            "to": resolved_to,
            "from_columns": [from_col],
            "to_columns": to_pk,
        }

    def _convert_metric(self, metric_def: dict, model_map: dict) -> Optional[dict]:
        mtype = metric_def.get("type")
        name = metric_def["name"]
        params = metric_def.get("type_params", {})

        if mtype == "conversion":
            return None

        metric: dict[str, Any] = {
            "name": name,
            "expression": {
                "dialects": [{
                    "dialect": "ANSI_SQL",
                    "expression": "",
                }],
            },
        }

        if mtype == "simple":
            measure_name = params.get("measure", name)
            metric["expression"]["dialects"][0]["expression"] = measure_name
            metric["custom_extensions"] = [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": json.dumps({"kind": "metric", "metric_type": "simple", "measure": measure_name}),
                }
            ]

        elif mtype == "ratio":
            num = params.get("numerator", {})
            den = params.get("denominator", {})
            num_name = num.get("name", "?")
            den_name = den.get("name", "?")
            metric["expression"]["dialects"][0]["expression"] = f"{num_name} / NULLIF({den_name}, 0)"
            metric["custom_extensions"] = [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": json.dumps({
                        "kind": "metric", "metric_type": "ratio",
                        "numerator": num_name, "denominator": den_name,
                    }),
                }
            ]

        elif mtype == "derived":
            expr = params.get("expr", "")
            metric["expression"]["dialects"][0]["expression"] = expr
            metric["custom_extensions"] = [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": json.dumps({"kind": "metric", "metric_type": "derived"}),
                }
            ]

        elif mtype == "cumulative":
            measure = params.get("measure", name)
            window = params.get("window")
            grain_to_date = params.get("grain_to_date")
            metric["expression"]["dialects"][0]["expression"] = measure
            metric["custom_extensions"] = [
                {
                    "vendor_name": "DBT_METRICFLOW",
                    "data": json.dumps({
                        "kind": "metric", "metric_type": "cumulative",
                        "measure": measure, "window": window, "grain_to_date": grain_to_date,
                    }),
                }
            ]

        if metric_def.get("filter"):
            metric["description"] = f"filter: {metric_def['filter']}"

        return metric
