"""Convert GoodData declarative LDM to OSI semantic model."""

from __future__ import annotations

import json
from typing import Any

from ..base import BaseConverter
from .models import (
    GdAttribute,
    GdDataset,
    GdDateInstance,
    GdDeclarativeModel,
    GdFact,
    GdLabel,
    GdReference,
    gd_model_from_dict,
)

OSI_VERSION = "0.1.1"


class GoodDataImporter(BaseConverter):
    """Import from GoodData declarative LDM JSON to OSI semantic model dict."""

    VENDOR_NAME = "GOODDATA"

    def to_osi(self, native_model: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        model = gd_model_from_dict(native_model)
        model_name = kwargs.get("model_name", "gooddata_model")
        model_description = kwargs.get("model_description", "")
        data_source_id = kwargs.get("data_source_id")
        return gooddata_to_osi(model, model_name, model_description, data_source_id)

    def from_osi(self, osi_model: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("GoodData export uses GoodDataExporter")


def gooddata_to_osi(
    model: GdDeclarativeModel,
    model_name: str = "gooddata_model",
    model_description: str = "",
    data_source_id: str | None = None,
) -> dict[str, Any]:
    """Convert a GoodData declarative model to an OSI semantic model dict."""
    osi_datasets = []
    osi_relationships = []

    attr_source_col_map: dict[str, dict[str, str]] = {}
    for ds in model.ldm.datasets:
        attr_source_col_map[ds.id] = {a.id: a.source_column for a in ds.attributes}

    for ds in model.ldm.datasets:
        osi_ds, rels = _convert_dataset(ds, attr_source_col_map)
        osi_datasets.append(osi_ds)
        osi_relationships.extend(rels)

    for di in model.ldm.date_instances:
        osi_datasets.append(_convert_date_instance(di))

    semantic_model: dict[str, Any] = {
        "name": model_name,
        "datasets": osi_datasets,
    }
    if model_description:
        semantic_model["description"] = model_description
    if osi_relationships:
        semantic_model["relationships"] = osi_relationships

    extensions = []
    if data_source_id:
        extensions.append(
            {
                "vendor_name": "GOODDATA",
                "data": json.dumps({"data_source_id": data_source_id}),
            }
        )
    if extensions:
        semantic_model["custom_extensions"] = extensions

    return {
        "version": OSI_VERSION,
        "semantic_model": [semantic_model],
    }


def _convert_dataset(
    ds: GdDataset,
    attr_source_col_map: dict[str, dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = _build_source(ds)
    primary_key = [attr.source_column for attr in ds.attributes if any(g.id == attr.id for g in ds.grain)]

    fields: list[dict[str, Any]] = []
    for attr in ds.attributes:
        fields.append(_convert_attribute(attr, ds.id))
    for fact in ds.facts:
        fields.append(_convert_fact(fact, ds.id))

    osi_ds: dict[str, Any] = {
        "name": ds.id,
        "source": source,
    }
    if primary_key:
        osi_ds["primary_key"] = primary_key
    if ds.description:
        osi_ds["description"] = ds.description
    if ds.title != ds.id:
        osi_ds["ai_context"] = {"synonyms": [ds.title]}
    if fields:
        osi_ds["fields"] = fields

    relationships = []
    for ref in ds.references:
        rel = _convert_reference(ds.id, ref, attr_source_col_map)
        relationships.append(rel)

    return osi_ds, relationships


def _convert_date_instance(di: GdDateInstance) -> dict[str, Any]:
    osi_ds: dict[str, Any] = {
        "name": di.id,
        "source": di.id,
    }
    if di.description:
        osi_ds["description"] = di.description
    if di.title != di.id:
        osi_ds["ai_context"] = {"synonyms": [di.title]}

    ext_data: dict[str, Any] = {
        "date_dimension": True,
        "granularities": di.granularities,
    }
    osi_ds["custom_extensions"] = [
        {"vendor_name": "GOODDATA", "data": json.dumps(ext_data)},
    ]

    return osi_ds


def _convert_attribute(attr: GdAttribute, dataset_id: str) -> dict[str, Any]:
    osi_field: dict[str, Any] = {
        "name": attr.source_column,
        "expression": {
            "dialects": [
                {"dialect": "ANSI_SQL", "expression": attr.source_column},
                {"dialect": "MAQL", "expression": f"{{label/{dataset_id}.{attr.id}}}"},
            ],
        },
        "dimension": {"is_time": False},
    }
    if attr.description:
        osi_field["description"] = attr.description
    if attr.title != attr.source_column:
        osi_field.setdefault("ai_context", {})["synonyms"] = [attr.title]

    ext = _build_attribute_extension(attr)
    if ext:
        osi_field["custom_extensions"] = [{"vendor_name": "GOODDATA", "data": json.dumps(ext)}]

    return osi_field


def _convert_fact(fact: GdFact, dataset_id: str) -> dict[str, Any]:
    osi_field: dict[str, Any] = {
        "name": fact.source_column,
        "expression": {
            "dialects": [
                {"dialect": "ANSI_SQL", "expression": fact.source_column},
                {"dialect": "MAQL", "expression": f"{{fact/{dataset_id}.{fact.id}}}"},
            ],
        },
    }
    if fact.description:
        osi_field["description"] = fact.description
    if fact.title != fact.source_column:
        osi_field.setdefault("ai_context", {})["synonyms"] = [fact.title]

    return osi_field


def _convert_reference(
    from_dataset: str,
    ref: GdReference,
    attr_source_col_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    to_dataset = ref.identifier.id
    target_cols_by_ds = attr_source_col_map.get(to_dataset, {})

    from_columns: list[str] = []
    to_columns: list[str] = []
    for s in ref.sources:
        from_columns.append(s.column)
        if s.target.type == "attribute":
            col = target_cols_by_ds.get(s.target.id)
            if col is None:
                raise ValueError(
                    f"Reference {from_dataset} -> {to_dataset}: target attribute "
                    f"'{s.target.id}' not found in target dataset."
                )
            to_columns.append(col)
        else:
            to_columns.append(s.column)

    rel: dict[str, Any] = {
        "name": f"{from_dataset}_to_{to_dataset}",
        "from": from_dataset,
        "to": to_dataset,
        "from_columns": from_columns,
        "to_columns": to_columns,
    }
    if ref.multivalue:
        rel["custom_extensions"] = [
            {"vendor_name": "GOODDATA", "data": json.dumps({"multivalue": True})},
        ]
    return rel


def _build_source(ds: GdDataset) -> str:
    if ds.data_source_table_id:
        t = ds.data_source_table_id
        if t.path:
            return ".".join([t.data_source_id, *t.path])
        return f"{t.data_source_id}.{t.id}"
    return ds.id


def _build_attribute_extension(attr: GdAttribute) -> dict[str, Any]:
    ext: dict[str, Any] = {"field_type": "attribute"}
    if attr.labels:
        ext["labels"] = [_label_ext(lb) for lb in attr.labels]
    if attr.sort_column:
        ext["sort_column"] = attr.sort_column
    if attr.sort_direction:
        ext["sort_direction"] = attr.sort_direction
    return ext


def _label_ext(lb: GdLabel) -> dict[str, Any]:
    d: dict[str, Any] = {"id": lb.id, "source_column": lb.source_column}
    if lb.value_type != "TEXT":
        d["value_type"] = lb.value_type
    return d
