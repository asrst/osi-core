from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

import json
import yaml
from pydantic import BaseModel

from .models import OsiModel, SemanticModel, Dataset, Field, Metric, Relationship
from .models.types import (
    AIContext,
    CustomExtension,
    DialectExpr,
    DialectExpression,
    Dialect,
    Dimension,
    Vendor,
)


def _load_raw(source: Union[Path, str], yaml_input: bool) -> Any:
    if isinstance(source, Path):
        text = source.read_text()
    elif isinstance(source, str) and (source.strip().startswith("{") or source.strip().startswith("[")) and not yaml_input:
        text = source
    elif isinstance(source, str) and (source.strip().startswith("---") or "\n" in source or ":" in source):
        text = source
    else:
        try:
            path = Path(source)
            if path.exists():
                text = path.read_text()
            else:
                text = source
        except Exception:
            text = source

    if yaml_input:
        return yaml.safe_load(text)

    return json.loads(text)


def load_osi_yaml(source: Union[Path, str]) -> dict:
    """Load OSI YAML from a file path or YAML string. Returns raw dict."""
    data = _load_raw(source, yaml_input=True)
    if not isinstance(data, dict):
        raise ValueError("OSI YAML must contain an object at the root")
    return data


def load_osi_json(source: Union[Path, str]) -> dict:
    """Load OSI JSON from a file path or JSON string. Returns raw dict."""
    data = _load_raw(source, yaml_input=False)
    if not isinstance(data, dict):
        raise ValueError("OSI JSON must contain an object at the root")
    return data


def dump_osi_yaml(data: Any, *, sort_keys: bool = False) -> str:
    """Dump OSI data to a YAML string."""
    if isinstance(data, BaseModel):
        data = data.model_dump()
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    if not isinstance(data, dict):
        raise ValueError("OSI data must be a mapping")
    return yaml.dump(data, default_flow_style=False, sort_keys=sort_keys)


def load_osi_model(source: Union[Path, str]) -> OsiModel:
    """Load OSI YAML and parse into an OsiModel in one step."""
    raw = load_osi_yaml(source)
    return _resolve(raw)


def dump_osi_model(model: OsiModel) -> str:
    """Serialize an OsiModel to OSI YAML."""
    data: dict[str, Any] = {
        "version": model.osi_spec_version,
        "semantic_model": [],
    }
    for sm in model.semantic_models:
        sm_data: dict[str, Any] = {
            "name": sm.name,
            "description": sm.description,
            "datasets": [],
            "relationships": [],
            "metrics": [],
        }
        for ds in sm.datasets:
            ds_data: dict[str, Any] = {
                "name": ds.name,
                "source": ds.source,
                "primary_key": ds.primary_key,
                "description": ds.description,
                "fields": [],
            }
            if ds.unique_keys:
                ds_data["unique_keys"] = ds.unique_keys
            for f in ds.fields:
                field_dict: dict[str, Any] = {
                    "name": f.name,
                    "expression": _expression_to_dict(f.expression),
                }
                if f.dimension is not None:
                    field_dict["dimension"] = {"is_time": f.dimension.is_time}
                if f.label is not None:
                    field_dict["label"] = f.label
                if f.description is not None:
                    field_dict["description"] = f.description
                if f.custom_extensions:
                    field_dict["custom_extensions"] = _extensions_to_dict(f.custom_extensions)
                if f.ai_context is not None:
                    field_dict["ai_context"] = _ai_context_to_dict(f.ai_context)
                ds_data["fields"].append(field_dict)
            if ds.custom_extensions:
                ds_data["custom_extensions"] = _extensions_to_dict(ds.custom_extensions)
            if ds.ai_context is not None:
                ds_data["ai_context"] = _ai_context_to_dict(ds.ai_context)
            sm_data["datasets"].append(ds_data)

        for rel in sm.relationships:
            rel_data: dict[str, Any] = {
                "name": rel.name,
                "from": rel.from_dataset,
                "to": rel.to_dataset,
                "from_columns": rel.from_columns,
                "to_columns": rel.to_columns,
            }
            if rel.custom_extensions:
                rel_data["custom_extensions"] = _extensions_to_dict(rel.custom_extensions)
            if rel.ai_context is not None:
                rel_data["ai_context"] = _ai_context_to_dict(rel.ai_context)
            sm_data["relationships"].append(rel_data)

        for m in sm.metrics:
            m_data: dict[str, Any] = {
                "name": m.name,
                "expression": _expression_to_dict(m.expression),
            }
            if m.description is not None:
                m_data["description"] = m.description
            if m.custom_extensions:
                m_data["custom_extensions"] = _extensions_to_dict(m.custom_extensions)
            if m.ai_context is not None:
                m_data["ai_context"] = _ai_context_to_dict(m.ai_context)
            sm_data["metrics"].append(m_data)

        if sm.custom_extensions:
            sm_data["custom_extensions"] = _extensions_to_dict(sm.custom_extensions)
        if sm.ai_context is not None:
            sm_data["ai_context"] = _ai_context_to_dict(sm.ai_context)

        data["semantic_model"].append(sm_data)

    if model.custom_extensions:
        data["custom_extensions"] = _extensions_to_dict(model.custom_extensions)
    if model.ai_context is not None:
        data["ai_context"] = _ai_context_to_dict(model.ai_context)

    return yaml.dump(data, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Internal helpers: resolve raw dict -> OsiModel
# ---------------------------------------------------------------------------


def _resolve(raw: dict) -> OsiModel:
    """Map OSI raw dict to OsiModel."""
    if "semantic_model" in raw:
        if isinstance(raw["semantic_model"], list) and len(raw["semantic_model"]) > 0:
            first_sm = raw["semantic_model"][0]
            if "datasets" in first_sm or "metrics" in first_sm or "relationships" in first_sm:
                return _resolve_osi_format(raw)
        raise ValueError("Unsupported semantic_model format")

    return _resolve_flat_format(raw)


def _resolve_osi_format(raw: dict) -> OsiModel:
    version = str(raw.get("version", "0.1.1"))
    semantic_models = []
    for sm_data in raw.get("semantic_model", []):
        datasets = _resolve_datasets(sm_data.get("datasets", []))
        relationships = _resolve_relationships(sm_data.get("relationships", []))
        metrics = _resolve_metrics(sm_data.get("metrics", []))
        ai_ctx = _resolve_ai_context(sm_data.get("ai_context"))

        semantic_models.append(SemanticModel(
            name=sm_data["name"],
            description=sm_data.get("description"),
            datasets=datasets,
            relationships=relationships,
            metrics=metrics,
            ai_context=ai_ctx,
            custom_extensions=_resolve_custom_extensions(sm_data.get("custom_extensions", [])),
        ))

    return OsiModel(
        osi_spec_version=version,
        name=raw.get("name") or (semantic_models[0].name if semantic_models else "unknown"),
        semantic_models=semantic_models,
        custom_extensions=_resolve_custom_extensions(raw.get("custom_extensions", [])),
        ai_context=_resolve_ai_context(raw.get("ai_context")),
    )


def _resolve_flat_format(raw: dict) -> OsiModel:
    datasets = []
    for ds_data in raw.get("datasets", []):
        fields = []
        for f_data in ds_data.get("fields", []):
            expr = _build_dialect_expression(f_data.get("expression", ""), f_data.get("type"))
            dim = None
            dim_data = f_data.get("dimension")
            is_time = False
            if "is_time" in f_data:
                is_time = bool(f_data["is_time"])
            elif isinstance(dim_data, dict):
                is_time = dim_data.get("is_time", False)
            if is_time:
                dim = Dimension(is_time=True)
            fields.append(Field(
                name=f_data["name"],
                expression=expr,
                dimension=dim,
                description=f_data.get("description"),
                custom_extensions=[],
            ))
        datasets.append(Dataset(
            name=ds_data["name"],
            source=ds_data.get("source", ""),
            primary_key=ds_data.get("primary_key", []),
            fields=fields,
            description=ds_data.get("description"),
            custom_extensions=[],
        ))

    metrics = []
    for m_data in raw.get("metrics", []):
        expr = _build_dialect_expression(m_data.get("expression", ""))
        metrics.append(Metric(
            name=m_data.get("name", ""),
            expression=expr,
            description=m_data.get("description"),
            custom_extensions=[],
        ))

    relationships = []
    for rel_data in raw.get("relationships", []):
        relationships.append(Relationship(
            name=rel_data["name"],
            from_dataset=rel_data["from"],
            to_dataset=rel_data["to"],
            from_columns=rel_data.get("from_columns", []),
            to_columns=rel_data.get("to_columns", []),
            custom_extensions=[],
        ))

    sm = SemanticModel(
        name=raw.get("name", "unknown"),
        description=None,
        datasets=datasets,
        relationships=relationships,
        metrics=metrics,
    )

    return OsiModel(
        osi_spec_version=str(raw.get("version", "0.1.1")),
        name=raw.get("name", "unknown"),
        semantic_models=[sm],
        custom_extensions=_resolve_custom_extensions(raw.get("custom_extensions", [])),
    )


def _resolve_datasets(ds_list: list[dict]) -> list[Dataset]:
    datasets = []
    for ds_data in ds_list:
        fields = []
        for f_data in ds_data.get("fields", []):
            expr = _resolve_expression(f_data.get("expression"))
            dim_data = f_data.get("dimension")
            dim = None
            if dim_data is not None:
                dim = Dimension(is_time=dim_data.get("is_time", False) if isinstance(dim_data, dict) else False)
            fields.append(Field(
                name=f_data["name"],
                expression=expr,
                dimension=dim,
                label=f_data.get("label"),
                description=f_data.get("description"),
                custom_extensions=_resolve_custom_extensions(f_data.get("custom_extensions", [])),
                ai_context=_resolve_ai_context(f_data.get("ai_context")),
            ))
        datasets.append(Dataset(
            name=ds_data["name"],
            source=ds_data.get("source", ""),
            primary_key=ds_data.get("primary_key", []),
            unique_keys=ds_data.get("unique_keys", []),
            fields=fields,
            description=ds_data.get("description"),
            custom_extensions=_resolve_custom_extensions(ds_data.get("custom_extensions", [])),
            ai_context=_resolve_ai_context(ds_data.get("ai_context")),
        ))
    return datasets


def _resolve_relationships(rel_list: list[dict]) -> list[Relationship]:
    relationships = []
    for rel_data in rel_list:
        relationships.append(Relationship(
            name=rel_data["name"],
            from_dataset=rel_data["from"],
            to_dataset=rel_data["to"],
            from_columns=rel_data.get("from_columns", []),
            to_columns=rel_data.get("to_columns", []),
            custom_extensions=_resolve_custom_extensions(rel_data.get("custom_extensions", [])),
            ai_context=_resolve_ai_context(rel_data.get("ai_context")),
        ))
    return relationships


def _resolve_metrics(m_list: list[dict]) -> list[Metric]:
    metrics = []
    for m_data in m_list:
        metrics.append(Metric(
            name=m_data["name"],
            expression=_resolve_expression(m_data.get("expression")),
            description=m_data.get("description"),
            custom_extensions=_resolve_custom_extensions(m_data.get("custom_extensions", [])),
            ai_context=_resolve_ai_context(m_data.get("ai_context")),
        ))
    return metrics


def _resolve_expression(expr_data) -> DialectExpression:
    if isinstance(expr_data, dict) and "dialects" in expr_data:
        dialects = []
        for d in expr_data.get("dialects", []):
            dialects.append(DialectExpr(
                dialect=Dialect(d["dialect"]),
                expression=d["expression"],
            ))
        return DialectExpression(dialects=dialects)
    if isinstance(expr_data, str):
        return DialectExpression(dialects=[DialectExpr(dialect=Dialect.ANSI_SQL, expression=expr_data)])
    return DialectExpression(dialects=[])


def _build_dialect_expression(expression: str, type_hint: Optional[str] = None) -> DialectExpression:
    if not expression and type_hint:
        return DialectExpression(dialects=[DialectExpr(dialect=Dialect.ANSI_SQL, expression=type_hint)])
    return DialectExpression(dialects=[DialectExpr(dialect=Dialect.ANSI_SQL, expression=expression or "")])


def _resolve_ai_context(ctx) -> Optional[AIContext]:
    if ctx is None:
        return None
    if isinstance(ctx, str):
        return AIContext(instructions=ctx)
    if isinstance(ctx, dict):
        return AIContext(
            instructions=ctx.get("instructions"),
            synonyms=ctx.get("synonyms", []),
            examples=ctx.get("examples", []),
        )
    return None


def _resolve_custom_extensions(ext_list: list[dict]) -> list[CustomExtension]:
    extensions = []
    for ext_data in ext_list:
        extensions.append(CustomExtension(
            vendor_name=Vendor(ext_data["vendor_name"]),
            data=ext_data["data"],
        ))
    return extensions


# ---------------------------------------------------------------------------
# Internal helpers: convert OsiModel -> dict
# ---------------------------------------------------------------------------


def _expression_to_dict(expr: DialectExpression) -> dict:
    dialects = []
    for de in expr.dialects:
        dialects.append({
            "dialect": de.dialect.value,
            "expression": de.expression,
        })
    return {"dialects": dialects}


def _extensions_to_dict(extensions: list[CustomExtension]) -> list[dict]:
    return [
        {"vendor_name": e.vendor_name.value, "data": e.data}
        for e in extensions
    ]


def _ai_context_to_dict(ctx: AIContext) -> dict:
    d: dict[str, Any] = {}
    if ctx.instructions:
        d["instructions"] = ctx.instructions
    if ctx.synonyms:
        d["synonyms"] = ctx.synonyms
    if ctx.examples:
        d["examples"] = ctx.examples
    return d
