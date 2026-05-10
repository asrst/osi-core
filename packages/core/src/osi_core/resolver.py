from typing import List, Optional

from .models import ResolvedModel, SemanticModel, Dataset, Field, Metric, Relationship
from .models.types import (
    AIContext,
    CustomExtension,
    DialectExpr,
    DialectExpression,
    Dialect,
    Dimension,
    ParseResult,
    Vendor,
)


def resolve(parse_result: ParseResult) -> ResolvedModel:
    """Map platform-native dict to OSI-aligned ResolvedModel."""
    raw = parse_result.raw

    if "semantic_model" in raw:
        if isinstance(raw["semantic_model"], list) and len(raw["semantic_model"]) > 0:
            first_sm = raw["semantic_model"][0]
            if "datasets" in first_sm or "metrics" in first_sm or "relationships" in first_sm:
                return _resolve_osi_format(raw, parse_result)

        return _resolve_metricflow_format(raw, parse_result)

    return _resolve_flat_format(raw, parse_result)


def _resolve_osi_format(raw: dict, parse_result: ParseResult) -> ResolvedModel:
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

    return ResolvedModel(
        osi_spec_version=raw.get("version", parse_result.osi_spec_version),
        name=raw.get("name") or (semantic_models[0].name if semantic_models else "unknown"),
        semantic_models=semantic_models,
        custom_extensions=_resolve_custom_extensions(raw.get("custom_extensions", [])) + parse_result.custom_extensions,
        ai_context=_resolve_ai_context(raw.get("ai_context")),
    )


def _resolve_metricflow_format(raw: dict, parse_result: ParseResult) -> ResolvedModel:
    name = raw.get("name", "unknown")

    semantic_models = []
    for sm_data in raw.get("semantic_model", []):
        fields = []
        for dim_data in sm_data.get("dimensions", []):
            fields.append(Field(
                name=dim_data["name"],
                expression=DialectExpression(dialects=[
                    DialectExpr(dialect=Dialect.ANSI_SQL, expression=dim_data.get("name", ""))
                ]),
                dimension=Dimension(is_time=dim_data.get("type") == "time"),
                description=dim_data.get("description"),
                custom_extensions=[],
            ))
        for ent_data in sm_data.get("entities", []):
            fields.append(Field(
                name=ent_data["name"],
                expression=DialectExpression(dialects=[
                    DialectExpr(dialect=Dialect.ANSI_SQL, expression=ent_data.get("name", ""))
                ]),
                description=ent_data.get("description"),
                custom_extensions=[],
            ))
        for meas_data in sm_data.get("measures", []):
            fields.append(Field(
                name=meas_data["name"],
                expression=DialectExpression(dialects=[
                    DialectExpr(dialect=Dialect.ANSI_SQL, expression=meas_data.get("name", ""))
                ]),
                description=meas_data.get("description"),
                custom_extensions=[],
            ))

        datasets = [
            Dataset(
                name=sm_data.get("name", "unknown"),
                source="",
                fields=fields,
                description=sm_data.get("description"),
                custom_extensions=[],
            )
        ]

        semantic_models.append(SemanticModel(
            name=sm_data.get("name", "unknown"),
            description=sm_data.get("description"),
            datasets=datasets,
            relationships=[],
            metrics=[],
        ))

    top_level_metrics = []
    for m_data in raw.get("metrics", []):
        expr_str = m_data.get("expr", "")
        top_level_metrics.append(Metric(
            name=m_data.get("name", "unknown"),
            expression=DialectExpression(dialects=[
                DialectExpr(dialect=Dialect.ANSI_SQL, expression=expr_str)
            ]),
            description=m_data.get("description"),
            custom_extensions=[],
        ))

    if top_level_metrics and semantic_models:
        semantic_models[0].metrics.extend(top_level_metrics)

    return ResolvedModel(
        osi_spec_version=parse_result.osi_spec_version,
        name=name,
        semantic_models=semantic_models,
        custom_extensions=_resolve_custom_extensions(raw.get("custom_extensions", [])) + parse_result.custom_extensions,
    )


def _resolve_flat_format(raw: dict, parse_result: ParseResult) -> ResolvedModel:
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

    return ResolvedModel(
        osi_spec_version=raw.get("version", parse_result.osi_spec_version),
        name=raw.get("name", "unknown"),
        semantic_models=[sm],
        custom_extensions=_resolve_custom_extensions(raw.get("custom_extensions", [])) + parse_result.custom_extensions,
    )


def _resolve_datasets(ds_list: List[dict]) -> List[Dataset]:
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


def _resolve_relationships(rel_list: List[dict]) -> List[Relationship]:
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


def _resolve_metrics(m_list: List[dict]) -> List[Metric]:
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


def _resolve_custom_extensions(ext_list: List[dict]) -> List[CustomExtension]:
    extensions = []
    for ext_data in ext_list:
        extensions.append(CustomExtension(
            vendor_name=Vendor(ext_data["vendor_name"]),
            data=ext_data["data"],
        ))
    return extensions