from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models.types import Dialect, DialectExpr, DialectExpression


def coerce_to_dialect_expression(expression: str, dialect: Dialect = Dialect.ANSI_SQL) -> DialectExpression:
    return DialectExpression(dialects=[DialectExpr(dialect=dialect, expression=expression)])


def pick_best_dialect(expression: Any, preferred: List[Dialect] = [Dialect.SNOWFLAKE, Dialect.ANSI_SQL]) -> Optional[DialectExpr]:
    if isinstance(expression, dict) and "dialects" in expression:
        for preferred_dialect in preferred:
            for dialect_entry in expression.get("dialects", []):
                if dialect_entry.get("dialect") == preferred_dialect.value:
                    return DialectExpr(dialect=preferred_dialect, expression=dialect_entry.get("expression", ""))
        for dialect_entry in expression.get("dialects", []):
            try:
                return DialectExpr(dialect=Dialect(dialect_entry.get("dialect")), expression=dialect_entry.get("expression", ""))
            except Exception:
                continue
    if isinstance(expression, str):
        return DialectExpr(dialect=Dialect.ANSI_SQL, expression=expression)
    return None


def normalize_identifier(identifier: str) -> str:
    identifier = identifier.strip()
    if identifier.startswith('"') and identifier.endswith('"'):
        return identifier
    return identifier.upper()


def parse_source(source: str) -> Dict[str, Optional[str]]:
    parts = source.split('.')
    return {
        "database": parts[-3] if len(parts) == 3 else None,
        "schema": parts[-2] if len(parts) >= 2 else None,
        "table": parts[-1] if len(parts) >= 1 else None,
    }
