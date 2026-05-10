import json
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


class OsiAdapter(BaseAdapter):
    format_name = "osi"

    def parse(
        self, source: Union[Path, str], version: Optional[str] = None
    ) -> ParseResult:
        if isinstance(source, Path):
            with open(source) as f:
                raw = yaml.safe_load(f)
        else:
            raw = yaml.safe_load(source)

        detected_version = self._detect_version(raw, version)
        custom_extensions = self._extract_extensions(raw)

        return ParseResult(
            raw=raw,
            source_format=self.format_name,
            source_version=detected_version,
            custom_extensions=custom_extensions,
            osi_spec_version=raw.get("version", "0.1.1"),
        )

    def translate(
        self, model: ResolvedModel, target_version: Optional[str] = None
    ) -> str:
        output_version = target_version or model.osi_spec_version

        data = {
            "version": output_version,
            "semantic_model": [],
        }

        for sm in model.semantic_models:
            sm_data = {
                "name": sm.name,
                "description": sm.description,
                "datasets": [],
                "relationships": [],
                "metrics": [],
            }

            for ds in sm.datasets:
                ds_data = {
                    "name": ds.name,
                    "source": ds.source,
                    "primary_key": ds.primary_key,
                    "unique_keys": ds.unique_keys,
                    "description": ds.description,
                    "fields": [],
                }
                for f in ds.fields:
                    field_dict = {
                        "name": f.name,
                        "expression": _expression_to_dict(f.expression),
                    }
                    if f.dimension is not None:
                        field_dict["dimension"] = {"is_time": f.dimension.is_time}
                    if f.label is not None:
                        field_dict["label"] = f.label
                    if f.description is not None:
                        field_dict["description"] = f.description
                    ds_data["fields"].append(field_dict)
                sm_data["datasets"].append(ds_data)

            for rel in sm.relationships:
                sm_data["relationships"].append({
                    "name": rel.name,
                    "from": rel.from_dataset,
                    "to": rel.to_dataset,
                    "from_columns": rel.from_columns,
                    "to_columns": rel.to_columns,
                })

            for m in sm.metrics:
                sm_data["metrics"].append({
                    "name": m.name,
                    "expression": _expression_to_dict(m.expression),
                    "description": m.description,
                })

            data["semantic_model"].append(sm_data)

        data = self._apply_extensions(data, model)

        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def _detect_version(self, raw: dict, version: Optional[str]) -> str:
        if version:
            return version
        if "semantic_model" in raw:
            return "0.1.1"
        if "datasets" in raw or "metrics" in raw:
            return "legacy"
        return "unknown"

    def _extract_extensions(self, raw: dict) -> List[CustomExtension]:
        extensions = []
        for ext_data in raw.get("custom_extensions", []):
            extensions.append(CustomExtension(
                vendor_name=Vendor(ext_data["vendor_name"]),
                data=ext_data["data"],
            ))
        return extensions

    def _apply_extensions(
        self, data: dict, model: ResolvedModel
    ) -> dict:
        if model.custom_extensions:
            data["custom_extensions"] = [
                {"vendor_name": e.vendor_name.value, "data": e.data}
                for e in model.custom_extensions
            ]
        return data


def _expression_to_dict(expr: DialectExpression) -> dict:
    dialects = []
    for de in expr.dialects:
        dialects.append({
            "dialect": de.dialect.value,
            "expression": de.expression,
        })
    return {"dialects": dialects} if dialects else {"dialects": []}