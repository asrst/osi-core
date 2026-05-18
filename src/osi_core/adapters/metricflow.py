from pathlib import Path
from typing import List, Optional, Union

import yaml

from ..models import ResolvedModel, SemanticModel, Dataset, Field, Metric, Relationship
from ..models.types import (
    AIContext,
    CustomExtension,
    DialectExpr,
    DialectExpression,
    Dialect,
    Dimension,
    ParseResult,
    Vendor,
)
from .base import BaseAdapter


def _vendor_from_str(v: str) -> Vendor:
    try:
        return Vendor(v)
    except ValueError:
        return Vendor.COMMON


class MetricFlowAdapter(BaseAdapter):
    format_name = "metricflow"

    def parse(
        self, source: Union[Path, str], version: Optional[str] = None
    ) -> ParseResult:
        if isinstance(source, Path):
            with open(source) as f:
                raw = yaml.safe_load(f)
        else:
            raw = yaml.safe_load(source)

        custom_extensions = self._extract_extensions(raw)

        return ParseResult(
            raw=raw,
            source_format=self.format_name,
            source_version=version or "1.0",
            custom_extensions=custom_extensions,
            osi_spec_version="0.1.1",
        )

    def translate(
        self, model: ResolvedModel, target_version: Optional[str] = None
    ) -> str:
        data = {
            "name": model.name,
            "semantic_model": [],
            "metrics": [],
        }

        for sm in model.semantic_models:
            for ds in sm.datasets:
                sm_data = {
                    "name": ds.name,
                    "description": ds.description,
                    "entities": [],
                    "dimensions": [],
                    "measures": [],
                }

                for f in ds.fields:
                    if _is_entity_field(f):
                        sm_data["entities"].append({
                            "name": f.name,
                            "type": "string",
                            "description": f.description,
                        })
                    elif _is_measure_field(f):
                        sm_data["measures"].append({
                            "name": f.name,
                            "type": _infer_measure_type(f),
                            "description": f.description,
                        })
                    else:
                        sm_data["dimensions"].append({
                            "name": f.name,
                            "type": _infer_dimension_type(f),
                            "description": f.description,
                        })

                data["semantic_model"].append(sm_data)
                break

            for m in sm.metrics:
                expr_str = m.expression.dialects[0].expression if m.expression.dialects else ""
                metric_type = _map_additivity_to_type(m)
                data["metrics"].append({
                    "name": m.name,
                    "type": metric_type,
                    "expr": expr_str,
                    "description": m.description,
                })

        data = self._apply_extensions(data, model)

        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def _detect_version(self, raw: dict) -> str:
        return "1.0"

    def _extract_extensions(self, raw: dict) -> List[CustomExtension]:
        extensions = []
        for sm_data in raw.get("semantic_model", []):
            for ent in sm_data.get("entities", []):
                if "role" in ent:
                    extensions.append(CustomExtension(
                        vendor_name=Vendor.COMMON,
                        data='{"entity_role": "' + ent["role"] + '"}',
                    ))
        return extensions

    def _apply_extensions(
        self, data: dict, model: ResolvedModel
    ) -> dict:
        return data


def _is_entity_field(field: Field) -> bool:
    return field.name.endswith("_id") or field.name.endswith("_key")


def _is_measure_field(field: Field) -> bool:
    if field.dimension is not None:
        return False
    name_lower = field.name.lower()
    return any(
        w in name_lower
        for w in ["revenue", "amount", "count", "total", "sum", "avg"]
    )


def _infer_dimension_type(field: Field) -> str:
    if field.dimension and field.dimension.is_time:
        return "time"
    return "categorical"


def _infer_measure_type(field: Field) -> str:
    return "float"


def _map_additivity_to_type(metric: Metric) -> str:
    if not metric.expression.dialects:
        return "simple"
    expr_str = metric.expression.dialects[0].expression.lower()
    if "distinct" in expr_str or "/" in expr_str:
        return "derived_non_additive"
    return "simple"