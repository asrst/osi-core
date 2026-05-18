from __future__ import annotations

from typing import Any, Dict, Optional

from ..base import BaseConverter


SUPPORTED_VERSION = "0.1.1"


class OsiConversionError(Exception):
    """Raised when an OSI YAML cannot be converted to Snowflake format."""


class SnowflakeExporter(BaseConverter):
    """Export from OSI to Snowflake Cortex Analyst semantic model YAML dict.

    Usage:
        exporter = SnowflakeExporter()
        snowflake_dict = exporter.from_osi(osi_dict)
        # then yaml.dump(snowflake_dict, ...)
    """

    VENDOR_NAME = "SNOWFLAKE"

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Snowflake import not yet implemented")

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        version = str(osi_model.get("version", ""))
        if version != SUPPORTED_VERSION:
            raise OsiConversionError(
                f"Unsupported OSI specification version '{version}'. "
                f"Supported: {SUPPORTED_VERSION}"
            )

        semantic_models = osi_model.get("semantic_model", [])
        if not semantic_models:
            raise OsiConversionError("Missing 'semantic_model' in OSI model")

        if len(semantic_models) > 1:
            import warnings
            warnings.warn(
                f"OSI model contains {len(semantic_models)} semantic models; "
                f"only the first will be converted"
            )

        osi = semantic_models[0]
        return self._convert_model(osi)

    def _convert_model(self, osi: dict) -> dict:
        name = osi.get("name")
        if not name:
            raise OsiConversionError("Missing required 'name' field in semantic model")

        result: dict = {}
        result["name"] = name

        description = osi.get("description")
        ai_context = osi.get("ai_context")
        if isinstance(ai_context, str) and ai_context:
            description = f"{description}\n{ai_context}" if description else ai_context
        if description:
            result["description"] = description

        datasets = osi.get("datasets")
        if datasets:
            tables = [self._convert_dataset(ds) for ds in datasets]
            if tables:
                result["tables"] = tables

        relationships = osi.get("relationships")
        if relationships:
            converted_rels = [self._convert_relationship(rel) for rel in relationships]
            if converted_rels:
                result["relationships"] = converted_rels

        metrics = osi.get("metrics")
        if metrics:
            converted_metrics = []
            for m in metrics:
                converted = self._convert_named_expr(m, "metric")
                if converted is not None:
                    converted_metrics.append(converted)
            if converted_metrics:
                result["metrics"] = converted_metrics

        dropped_ai = ["ai_context"] if isinstance(ai_context, dict) and ai_context else []
        self._warn_dropped_fields(osi, "model", extra_dropped=dropped_ai)

        return result

    def _convert_dataset(self, dataset: dict) -> dict:
        result: dict = {}
        name = dataset.get("name")
        if not name:
            raise OsiConversionError("Missing required 'name' field in dataset")
        result["name"] = name

        source = dataset.get("source")
        base_table = _parse_source(source)
        if base_table is not None:
            result["base_table"] = base_table

        pk = dataset.get("primary_key")
        if pk:
            result["primary_key"] = {"columns": pk}

        uks = dataset.get("unique_keys")
        if uks:
            result["unique_keys"] = [{"columns": uk} for uk in uks]

        description = dataset.get("description")
        ai_context = dataset.get("ai_context")
        if isinstance(ai_context, str) and ai_context:
            description = f"{description}\n{ai_context}" if description else ai_context
        if description:
            result["description"] = description

        synonyms = _extract_synonyms(ai_context)
        if synonyms:
            result["synonyms"] = synonyms

        fields = dataset.get("fields")
        if fields:
            dimensions = []
            time_dimensions = []
            facts = []

            for field in fields:
                classification = _classify_field(field)
                converted = self._convert_named_expr(field, "field")
                if converted is None:
                    continue
                if classification == "time_dimension":
                    time_dimensions.append(converted)
                elif classification == "dimension":
                    dimensions.append(converted)
                else:
                    facts.append(converted)

            if dimensions:
                result["dimensions"] = dimensions
            if time_dimensions:
                result["time_dimensions"] = time_dimensions
            if facts:
                result["facts"] = facts

        dropped_ai = []
        if isinstance(ai_context, dict):
            non_synonym_keys = [k for k in ai_context if k != "synonyms"]
            if non_synonym_keys:
                dropped_ai = [f"ai_context ({', '.join(non_synonym_keys)})"]
        self._warn_dropped_fields(dataset, f"dataset '{name}'", extra_dropped=dropped_ai)

        return result

    def _convert_named_expr(self, entry: dict, kind: str) -> Optional[dict]:
        name = entry.get("name")
        if not name:
            raise OsiConversionError(f"Missing required 'name' in {kind}")

        expr_str = _extract_expression(entry.get("expression"), name)
        if expr_str is None:
            return None

        result: dict = {}
        result["name"] = name
        result["expr"] = expr_str

        description = entry.get("description")
        ai_context = entry.get("ai_context")
        if isinstance(ai_context, str) and ai_context:
            description = f"{description}\n{ai_context}" if description else ai_context
        if description:
            result["description"] = description

        synonyms = _extract_synonyms(ai_context)
        if synonyms:
            result["synonyms"] = synonyms

        dropped_ai = []
        if isinstance(ai_context, dict):
            non_synonym_keys = [k for k in ai_context if k != "synonyms"]
            if non_synonym_keys:
                dropped_ai = [f"ai_context ({', '.join(non_synonym_keys)})"]
        self._warn_dropped_fields(entry, f"{kind} '{name}'", extra_dropped=dropped_ai)

        return result

    def _convert_relationship(self, rel: dict) -> dict:
        result: dict = {}
        rel_name = rel.get("name")
        if not rel_name:
            raise OsiConversionError("Missing required 'name' field in relationship")
        result["name"] = rel_name

        left_table = rel.get("from")
        if not left_table:
            raise OsiConversionError(f"Relationship '{rel_name}': missing required 'from' field")
        right_table = rel.get("to")
        if not right_table:
            raise OsiConversionError(f"Relationship '{rel_name}': missing required 'to' field")
        result["left_table"] = left_table
        result["right_table"] = right_table

        from_cols = rel.get("from_columns", [])
        to_cols = rel.get("to_columns", [])

        if len(from_cols) != len(to_cols):
            raise OsiConversionError(
                f"Relationship '{rel_name}': from_columns and to_columns must have the "
                f"same length (got {len(from_cols)} and {len(to_cols)})"
            )

        relationship_columns = [
            {"left_column": fc, "right_column": tc}
            for fc, tc in zip(from_cols, to_cols)
        ]
        if relationship_columns:
            result["relationship_columns"] = relationship_columns

        dropped_ai = ["ai_context"] if rel.get("ai_context") else []
        self._warn_dropped_fields(rel, f"relationship '{rel_name}'", extra_dropped=dropped_ai)

        return result

    @staticmethod
    def _warn_dropped_fields(source: dict, context: str, extra_dropped: Optional[list[str]] = None) -> None:
        import warnings
        dropped = list(extra_dropped) if extra_dropped else []
        if source.get("custom_extensions"):
            dropped.append("custom_extensions")
        if source.get("version"):
            dropped.append("version")
        if source.get("label"):
            dropped.append("label")
        if dropped:
            warnings.warn(
                f"Dropped from {context} (no Snowflake counterpart): "
                + ", ".join(dropped)
            )


# ---------------------------------------------------------------------------
# Module-level helper functions (shared with importer)
# ---------------------------------------------------------------------------


def _classify_field(field: dict) -> str:
    dimension = field.get("dimension")
    if dimension is None:
        return "fact"
    if isinstance(dimension, dict) and dimension.get("is_time") is True:
        return "time_dimension"
    return "dimension"


def _extract_expression(expression: Any, field_name: str) -> Optional[str]:
    if expression is None or not isinstance(expression, dict):
        raise OsiConversionError(
            f"Missing or malformed expression for field/metric '{field_name}'"
        )

    dialects = expression.get("dialects")
    if not dialects:
        raise OsiConversionError(
            f"Missing expression for field/metric '{field_name}'"
        )

    snowflake_expr = None
    ansi_expr = None

    for d in dialects:
        dialect_name = (d.get("dialect") or "").upper()
        if dialect_name == "SNOWFLAKE":
            snowflake_expr = d.get("expression")
        elif dialect_name == "ANSI_SQL":
            ansi_expr = d.get("expression")

    if snowflake_expr is not None:
        return snowflake_expr
    if ansi_expr is not None:
        return ansi_expr

    import warnings
    dialect_names = [d.get("dialect", "") for d in dialects]
    warnings.warn(
        f"Skipping field/metric '{field_name}': no Snowflake-compatible expression "
        f"(has dialects: {', '.join(dialect_names)}; requires SNOWFLAKE or ANSI_SQL)"
    )
    return None


def _normalize_identifier(identifier: str) -> str:
    stripped = identifier.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        return stripped
    return stripped.upper()


def _parse_source(source: Optional[str]) -> Optional[dict]:
    if not source:
        return None

    source_stripped = str(source).strip()
    if not source_stripped:
        return None

    upper = source_stripped.upper()
    if upper.startswith(("SELECT ", "SELECT\n", "SELECT\t",
                          "WITH ", "WITH\n", "WITH\t")):
        return {"definition": source_stripped}

    parts = source_stripped.split(".")
    if len(parts) == 3:
        return {
            "database": _normalize_identifier(parts[0]),
            "schema": _normalize_identifier(parts[1]),
            "table": _normalize_identifier(parts[2]),
        }

    raise OsiConversionError(
        f"Source '{source}' must be a fully qualified db.schema.table or a subquery"
    )


def _extract_synonyms(ai_context: Any) -> Optional[list[str]]:
    if isinstance(ai_context, dict):
        synonyms = ai_context.get("synonyms")
        if isinstance(synonyms, list) and synonyms:
            return list(synonyms)
    return None
