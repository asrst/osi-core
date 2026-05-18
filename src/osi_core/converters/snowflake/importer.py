from __future__ import annotations

from typing import Any, Dict, Optional

from ..base import BaseConverter
from ...normalizer import normalize_identifier
from .exporter import _extract_synonyms


class SnowflakeImporter(BaseConverter):
    """Import from Snowflake Cortex Analyst YAML to OSI semantic model dict.

    Usage:
        importer = SnowflakeImporter()
        osi_dict = importer.to_osi(snowflake_dict)
        # then validate/serialize with osi_core.serializer
    """

    VENDOR_NAME = "SNOWFLAKE"

    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return self._convert_to_osi(native_model)

    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Snowflake export uses SnowflakeExporter")

    def _convert_to_osi(self, snowflake: dict) -> dict:
        datasets = []
        relationships = []
        metrics = []

        for table in snowflake.get("tables", []):
            ds = self._convert_table(table)
            datasets.append(ds)

        for rel in snowflake.get("relationships", []):
            relationships.append(self._convert_relationship(rel))

        for metric in snowflake.get("metrics", []):
            metrics.append(self._convert_metric(metric))

        first_sm: dict[str, Any] = {
            "name": snowflake.get("name", "imported_model"),
            "datasets": datasets,
        }
        if snowflake.get("description"):
            first_sm["description"] = snowflake["description"]
        if relationships:
            first_sm["relationships"] = relationships
        if metrics:
            first_sm["metrics"] = metrics

        return {
            "version": "0.1.1",
            "semantic_model": [first_sm],
        }

    def _convert_table(self, table: dict) -> dict:
        name = table.get("name", "")
        source = self._reverse_source(table.get("base_table"))

        fields = []
        for dim in table.get("dimensions", []):
            fields.append(self._convert_field(dim, is_dimension=True, is_time=False))
        for td in table.get("time_dimensions", []):
            fields.append(self._convert_field(td, is_dimension=True, is_time=True))
        for fact in table.get("facts", []):
            fields.append(self._convert_field(fact, is_dimension=False, is_time=False))

        ds = {
            "name": name,
            "source": source or name,
            "fields": fields,
        }

        pk = table.get("primary_key")
        if pk and "columns" in pk:
            ds["primary_key"] = pk["columns"]

        uks = table.get("unique_keys")
        if uks:
            ds["unique_keys"] = [uk["columns"] for uk in uks if "columns" in uk]

        if table.get("description"):
            ds["description"] = table["description"]

        synonyms = table.get("synonyms")
        if synonyms:
            ds["ai_context"] = {"synonyms": synonyms}

        return ds

    def _convert_field(self, entry: dict, is_dimension: bool, is_time: bool) -> dict:
        field: dict = {
            "name": entry.get("name", ""),
            "expression": {
                "dialects": [
                    {
                        "dialect": "ANSI_SQL",
                        "expression": entry.get("expr", ""),
                    }
                ]
            },
        }
        if is_dimension:
            field["dimension"] = {"is_time": is_time}
        if entry.get("description"):
            field["description"] = entry["description"]
        synonyms = _extract_synonyms({"synonyms": entry.get("synonyms", [])})
        if synonyms:
            field["ai_context"] = {"synonyms": synonyms}
        return field

    def _convert_relationship(self, rel: dict) -> dict:
        from_cols = []
        to_cols = []
        for rc in rel.get("relationship_columns", []):
            from_cols.append(rc.get("left_column", ""))
            to_cols.append(rc.get("right_column", ""))

        return {
            "name": rel.get("name", ""),
            "from": rel.get("left_table", ""),
            "to": rel.get("right_table", ""),
            "from_columns": from_cols,
            "to_columns": to_cols,
        }

    def _convert_metric(self, metric: dict) -> dict:
        m: dict = {
            "name": metric.get("name", ""),
            "expression": {
                "dialects": [
                    {
                        "dialect": "ANSI_SQL",
                        "expression": metric.get("expr", ""),
                    }
                ]
            },
        }
        if metric.get("description"):
            m["description"] = metric["description"]
        synonyms = _extract_synonyms({"synonyms": metric.get("synonyms", [])})
        if synonyms:
            m["ai_context"] = {"synonyms": synonyms}
        return m

    @staticmethod
    def _reverse_source(base_table: Optional[dict]) -> Optional[str]:
        if base_table is None:
            return None
        if "definition" in base_table:
            return base_table["definition"]
        db = base_table.get("database", "")
        schema = base_table.get("schema", "")
        table = base_table.get("table", "")
        if db and schema and table:
            return f"{db}.{schema}.{table}".lower() if (not db.startswith('"') and not table.endswith('"')) else f"{db}.{schema}.{table}"
        return None
