"""Convert OSI semantic model to GoodData declarative LDM."""

from __future__ import annotations

import json
import re
from typing import Any

from ..base import BaseConverter
from .models import (
    GdAttribute,
    GdDataset,
    GdDataSourceTableId,
    GdDateInstance,
    GdDeclarativeModel,
    GdFact,
    GdGrain,
    GdGranularitiesFormatting,
    GdLabel,
    GdLdm,
    GdReference,
    GdReferenceIdentifier,
    GdReferenceSource,
    GdReferenceTarget,
    gd_model_to_dict,
)

_MAQL_LABEL_RE = re.compile(r"\{label/([^.]+)\.([^}]+)\}")
_MAQL_FACT_RE = re.compile(r"\{fact/([^.]+)\.([^}]+)\}")


class GoodDataExporter(BaseConverter):
    """Export from OSI semantic model to GoodData declarative LDM JSON dict."""

    VENDOR_NAME = "GOODDATA"

    def to_osi(self, native_model: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("GoodData import uses GoodDataImporter")

    def from_osi(self, osi_model: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        data_source_id = kwargs.get("data_source_id", "default")
        model = osi_to_gooddata(osi_model, data_source_id)
        return gd_model_to_dict(model)


def osi_to_gooddata(
    osi_model: dict[str, Any],
    data_source_id: str = "default",
) -> GdDeclarativeModel:
    """Convert an OSI semantic model dict to a GoodData declarative model."""
    datasets: list[GdDataset] = []
    date_instances: list[GdDateInstance] = []

    for sm in osi_model.get("semantic_model", []):
        relationship_map = _build_relationship_map(sm)
        target_info = _build_target_info(sm)

        for ds in sm.get("datasets", []):
            gd_ds, date_inst = _convert_osi_dataset(
                ds, relationship_map, target_info, data_source_id,
            )
            if date_inst:
                date_instances.append(date_inst)
            else:
                datasets.append(gd_ds)

    return GdDeclarativeModel(ldm=GdLdm(datasets=datasets, date_instances=date_instances))


def _build_target_info(sm: dict[str, Any]) -> dict[str, dict[str, Any]]:
    info: dict[str, dict[str, Any]] = {}
    for ds in sm.get("datasets", []):
        ds_name = ds["name"]
        is_date = _is_date_dataset(ds)
        col_to_attr: dict[str, str] = {}
        if not is_date:
            for f in ds.get("fields", []):
                src = _get_source_column(f)
                col_to_attr[src] = f"attr.{ds_name}.{f['name']}"
        info[ds_name] = {"is_date": is_date, "col_to_attr": col_to_attr}
    return info


def _is_date_dataset(ds: dict[str, Any]) -> bool:
    gd_ext = _get_gooddata_extension(ds)
    if gd_ext and gd_ext.get("date_dimension"):
        return True
    fields = ds.get("fields", [])
    return bool(fields) and all(_is_time_field(f) for f in fields) and not gd_ext


def _build_relationship_map(
    sm: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    rel_map: dict[str, list[dict[str, Any]]] = {}
    for rel in sm.get("relationships", []):
        from_ds = rel["from"]
        rel_map.setdefault(from_ds, []).append(rel)
    return rel_map


def _convert_osi_dataset(
    ds: dict[str, Any],
    relationship_map: dict[str, list[dict[str, Any]]],
    target_info: dict[str, dict[str, Any]],
    data_source_id: str,
) -> tuple[GdDataset, GdDateInstance | None]:
    ds_name = ds["name"]
    source = ds.get("source", ds_name)

    gd_ext = _get_gooddata_extension(ds)
    if gd_ext and gd_ext.get("date_dimension"):
        return _placeholder_dataset(ds_name), _convert_to_date_instance(ds, gd_ext)

    fields = ds.get("fields", [])
    all_time = fields and all(_is_time_field(f) for f in fields)
    if all_time and not gd_ext:
        return _placeholder_dataset(ds_name), _convert_to_date_instance_from_fields(ds)

    attributes: list[GdAttribute] = []
    facts: list[GdFact] = []
    grain_ids: list[str] = []

    pk_columns = set(ds.get("primary_key", []))

    for field_def in fields:
        field_name = field_def["name"]
        is_dimension = field_def.get("dimension") is not None

        if is_dimension:
            attr = _convert_to_attribute(field_def, ds_name)
            attributes.append(attr)
            if field_name in pk_columns:
                grain_ids.append(attr.id)
        else:
            maql_type = _detect_type_from_maql(field_def)
            if maql_type == "attribute":
                attr = _convert_to_attribute(field_def, ds_name)
                attributes.append(attr)
                if field_name in pk_columns:
                    grain_ids.append(attr.id)
            else:
                facts.append(_convert_to_fact(field_def, ds_name))

    grain = [GdGrain(id=gid, type="attribute") for gid in grain_ids]

    references = []
    for rel in relationship_map.get(ds_name, []):
        references.append(_convert_relationship(rel, target_info))

    ds_table_id = _parse_source_to_table_id(source, data_source_id)

    return (
        GdDataset(
            id=ds_name,
            title=_get_title(ds),
            grain=grain,
            references=references,
            attributes=attributes,
            facts=facts,
            description=ds.get("description", ""),
            data_source_table_id=ds_table_id,
        ),
        None,
    )


def _convert_to_date_instance(ds: dict[str, Any], gd_ext: dict[str, Any]) -> GdDateInstance:
    return GdDateInstance(
        id=ds["name"],
        title=_get_title(ds),
        description=ds.get("description", ""),
        granularities=gd_ext.get("granularities", ["DAY", "WEEK", "MONTH", "QUARTER", "YEAR"]),
        granularities_formatting=GdGranularitiesFormatting(),
    )


def _convert_to_date_instance_from_fields(ds: dict[str, Any]) -> GdDateInstance:
    return GdDateInstance(
        id=ds["name"],
        title=_get_title(ds),
        description=ds.get("description", ""),
        granularities=["DAY", "WEEK", "MONTH", "QUARTER", "YEAR"],
        granularities_formatting=GdGranularitiesFormatting(),
    )


def _convert_to_attribute(field_def: dict[str, Any], dataset_id: str) -> GdAttribute:
    field_name = field_def["name"]
    source_col = _get_source_column(field_def)
    attr_id = f"attr.{dataset_id}.{field_name}"

    gd_ext = _get_gooddata_extension(field_def)
    labels: list[GdLabel] = []
    if gd_ext and "labels" in gd_ext:
        for lb_def in gd_ext["labels"]:
            labels.append(
                GdLabel(
                    id=lb_def["id"],
                    title=lb_def.get("title", lb_def["id"]),
                    source_column=lb_def.get("source_column", source_col),
                    value_type=lb_def.get("value_type", "TEXT"),
                )
            )

    return GdAttribute(
        id=attr_id,
        title=_get_title(field_def, fallback=field_name),
        source_column=source_col,
        description=field_def.get("description", ""),
        sort_column=gd_ext.get("sort_column") if gd_ext else None,
        sort_direction=gd_ext.get("sort_direction") if gd_ext else None,
        labels=labels,
    )


def _convert_to_fact(field_def: dict[str, Any], dataset_id: str) -> GdFact:
    field_name = field_def["name"]
    source_col = _get_source_column(field_def)

    return GdFact(
        id=f"fact.{dataset_id}.{field_name}",
        title=_get_title(field_def, fallback=field_name),
        source_column=source_col,
        description=field_def.get("description", ""),
    )


def _get_source_column(field_def: dict[str, Any]) -> str:
    for dialect_expr in field_def.get("expression", {}).get("dialects", []):
        if dialect_expr.get("dialect") == "ANSI_SQL":
            return dialect_expr["expression"]
    return field_def["name"]


def _detect_type_from_maql(field_def: dict[str, Any]) -> str:
    for dialect_expr in field_def.get("expression", {}).get("dialects", []):
        if dialect_expr.get("dialect") == "MAQL":
            expr = dialect_expr["expression"]
            if _MAQL_FACT_RE.search(expr):
                return "fact"
            if _MAQL_LABEL_RE.search(expr):
                return "attribute"
    return "fact"


def _get_gooddata_extension(obj: dict[str, Any]) -> dict[str, Any] | None:
    for ext in obj.get("custom_extensions", []):
        if ext.get("vendor_name") == "GOODDATA":
            data = ext.get("data", "{}")
            if isinstance(data, str):
                return json.loads(data)
            return data
    return None


def _get_title(obj: dict[str, Any], fallback: str = "") -> str:
    ctx = obj.get("ai_context")
    if isinstance(ctx, dict):
        synonyms = ctx.get("synonyms", [])
        if synonyms:
            return synonyms[0]
    return obj.get("description", "") or obj.get("name", "") or fallback


def _is_time_field(field_def: dict[str, Any]) -> bool:
    dim = field_def.get("dimension")
    return isinstance(dim, dict) and dim.get("is_time") is True


def _convert_relationship(
    rel: dict[str, Any],
    target_info: dict[str, dict[str, Any]],
) -> GdReference:
    to_ds = rel["to"]
    from_columns: list[str] = rel.get("from_columns", [])
    to_columns: list[str] = rel.get("to_columns", from_columns)

    target_meta = target_info.get(to_ds, {"is_date": False, "col_to_attr": {}})
    sources: list[GdReferenceSource] = []
    for from_col, to_col in zip(from_columns, to_columns):
        if target_meta["is_date"]:
            target = GdReferenceTarget(id=to_ds, type="date")
        else:
            attr_id = target_meta["col_to_attr"].get(to_col)
            if attr_id is None:
                raise ValueError(
                    f"Relationship '{rel.get('name', from_col)}': target column "
                    f"'{to_col}' not found as a field of dataset '{to_ds}'."
                )
            target = GdReferenceTarget(id=attr_id, type="attribute")
        sources.append(GdReferenceSource(column=from_col, target=target))

    return GdReference(
        identifier=GdReferenceIdentifier(id=to_ds, type="dataset"),
        sources=sources,
        multivalue=_is_multivalue(rel),
    )


def _is_multivalue(rel: dict[str, Any]) -> bool:
    gd_ext = _get_gooddata_extension(rel)
    return bool(gd_ext and gd_ext.get("multivalue"))


def _parse_source_to_table_id(source: str, data_source_id: str) -> GdDataSourceTableId:
    parts = source.split(".")
    if len(parts) >= 3:
        return GdDataSourceTableId(
            id=parts[-1],
            data_source_id=parts[0],
            path=parts[1:],
        )
    if len(parts) == 2:
        return GdDataSourceTableId(
            id=parts[-1],
            data_source_id=parts[0],
            path=[parts[-1]],
        )
    return GdDataSourceTableId(
        id=source,
        data_source_id=data_source_id,
    )


def _placeholder_dataset(name: str) -> GdDataset:
    return GdDataset(id=name, title=name)
