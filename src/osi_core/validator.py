from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator
from sqlglot import parse_one
from sqlglot.errors import ParseError


from .dialects import DIALECT_MAP

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "osi-schema.json"


def _load_schema() -> Dict[str, Any]:
    with SCHEMA_PATH.open() as f:
        return json.load(f)


def validate_schema(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    try:
        schema = _load_schema()
    except FileNotFoundError as exc:
        raise RuntimeError("OSI JSON schema not found") from exc

    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.path)
        if path:
            errors.append(f"{path}: {error.message}")
        else:
            errors.append(error.message)

    if isinstance(data, dict):
        errors.extend(_validate_semantic_model(data))

    return errors


def _validate_semantic_model(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    semantic_models = data.get("semantic_model", [])
    if not isinstance(semantic_models, list):
        return errors

    for sm_index, sm in enumerate(semantic_models):
        if not isinstance(sm, dict):
            errors.append(f"semantic_model[{sm_index}] must be an object")
            continue

        dataset_names = set()
        relationship_names = set()
        metric_names = set()
        dataset_fields: Dict[str, set[str]] = {}

        for ds_index, ds in enumerate(sm.get("datasets", [])):
            if not isinstance(ds, dict):
                errors.append(
                    f"semantic_model[{sm_index}].datasets[{ds_index}] must be an object")
                continue
            name = ds.get("name")
            if not name:
                errors.append(
                    f"semantic_model[{sm_index}].datasets[{ds_index}].name is required")
                continue
            if name in dataset_names:
                errors.append(f"Duplicate dataset name: {name}")
            dataset_names.add(name)

            fields = ds.get("fields", [])
            field_names = set()
            for f_index, f in enumerate(fields):
                if not isinstance(f, dict):
                    errors.append(
                        f"semantic_model[{sm_index}].datasets[{ds_index}].fields[{f_index}] must be an object")
                    continue
                field_name = f.get("name")
                if not field_name:
                    errors.append(
                        f"semantic_model[{sm_index}].datasets[{ds_index}].fields[{f_index}].name is required")
                    continue
                if field_name in field_names:
                    errors.append(
                        f"Duplicate field name in dataset {name}: {field_name}")
                field_names.add(field_name)
                _validate_expression(f.get(
                    "expression"), errors, f"semantic_model[{sm_index}].datasets[{ds_index}].fields[{f_index}].expression")
            dataset_fields[name] = field_names

        for rel_index, rel in enumerate(sm.get("relationships", [])):
            if not isinstance(rel, dict):
                errors.append(
                    f"semantic_model[{sm_index}].relationships[{rel_index}] must be an object")
                continue
            rel_name = rel.get("name")
            from_dataset = rel.get("from")
            to_dataset = rel.get("to")
            if not rel_name:
                errors.append(
                    f"semantic_model[{sm_index}].relationships[{rel_index}].name is required")
            if from_dataset not in dataset_names:
                errors.append(
                    f"Relationship {rel_name or rel_index} refers to unknown from dataset: {from_dataset}")
            if to_dataset not in dataset_names:
                errors.append(
                    f"Relationship {rel_name or rel_index} refers to unknown to dataset: {to_dataset}")
            from_columns = rel.get("from_columns", [])
            to_columns = rel.get("to_columns", [])
            if len(from_columns) != len(to_columns):
                errors.append(
                    f"Relationship {rel_name or rel_index} has mismatched from_columns/to_columns lengths")
            if from_dataset in dataset_fields:
                for column in from_columns:
                    if column not in dataset_fields[from_dataset]:
                        errors.append(
                            f"Relationship {rel_name or rel_index} references unknown column {column} in dataset {from_dataset}")
            if to_dataset in dataset_fields:
                for column in to_columns:
                    if column not in dataset_fields[to_dataset]:
                        errors.append(
                            f"Relationship {rel_name or rel_index} references unknown column {column} in dataset {to_dataset}")

        for metric_index, metric in enumerate(sm.get("metrics", [])):
            if not isinstance(metric, dict):
                errors.append(
                    f"semantic_model[{sm_index}].metrics[{metric_index}] must be an object")
                continue
            name = metric.get("name")
            if not name:
                errors.append(
                    f"semantic_model[{sm_index}].metrics[{metric_index}].name is required")
                continue
            if name in metric_names:
                errors.append(f"Duplicate metric name: {name}")
            metric_names.add(name)
            _validate_expression(metric.get(
                "expression"), errors, f"semantic_model[{sm_index}].metrics[{metric_index}].expression")

    return errors


def _validate_expression(expression: Any, errors: List[str], context: str) -> None:
    if isinstance(expression, dict) and "dialects" in expression:
        for dialect_entry in expression.get("dialects", []):
            dialect = dialect_entry.get("dialect")
            expr_text = dialect_entry.get("expression")
            if isinstance(dialect, str) and isinstance(expr_text, str):
                _validate_sql(expr_text, dialect, errors, context)
            else:
                errors.append(f"{context}: invalid dialect entry")
    elif isinstance(expression, str):
        _validate_sql(expression, "ANSI_SQL", errors, context)


def _validate_sql(expression: str, dialect: str, errors: List[str], context: str) -> None:
    if dialect == "ANSI_SQL":
        dialect_name = None
    else:
        dialect_name = DIALECT_MAP.get(dialect)
        if dialect_name is None:
            return
    try:
        parse_one(expression, read=dialect_name)
    except (ParseError, ValueError) as exc:
        errors.append(f"{context} [{dialect}]: SQL parse error: {exc}")


def validate_osi_version(data: Dict[str, Any]) -> Optional[str]:
    return data.get("version")
