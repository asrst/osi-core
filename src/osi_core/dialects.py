from __future__ import annotations

from typing import Any, Optional

DIALECT_MAP: dict[str, str] = {
    "ANSI_SQL": "sql",
    "SNOWFLAKE": "snowflake",
    "DATABRICKS": "databricks",
}


def select_dialect(
    expression: Any,
    preferred: list[str] | None = None,
) -> Optional[str]:
    if not isinstance(expression, dict):
        return None
    dialects = expression.get("dialects") if isinstance(expression, dict) else []
    if not dialects:
        return None

    preferred = preferred or ["ANSI_SQL", "SNOWFLAKE"]
    dialect_map = {d.get("dialect"): d.get("expression") for d in dialects if isinstance(d, dict)}

    for name in preferred:
        if name in dialect_map:
            return dialect_map[name]

    for name in dialect_map:
        return dialect_map[name]

    return None
