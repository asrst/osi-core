# Developer Guide

## Setup

```bash
# Clone and install all dependencies
cd /workspaces/semetric
uv sync
```

## Project Structure

```
packages/
├── core/                         # osi-core package
│   ├── src/semetric_core/
│   │   ├── models/
│   │   │   ├── resolved.py      # ResolvedModel (OSI v0.1.1 aligned)
│   │   │   ├── parse_result.py  # ParseResult model
│   │   │   └── types.py         # Enums: Dialect, Vendor, Additivity, etc.
│   │   ├── resolver.py           # ParseResult → ResolvedModel
│   │   ├── translator.py        # Orchestrates adapter + resolver
│   │   ├── registry.py         # Adapter discovery
│   │   ├── diff.py             # Change detection
│   │   ├── cli.py              # CLI commands
│   │   └── adapters/           # Adapter base class (if needed in core)
│   └── tests/
│       └── fixtures/           # Test YAML files
├── osi-adapter/                 # OSI format adapter (separate package)
│   ├── src/semetric_osi_adapter/
│   │   └── adapter.py
│   ├── tests/
│   ├── fixtures/
│   └── pyproject.toml          # Independent package version
├── metricflow-adapter/          # (future)
├── snowflake-adapter/           # (future)
└── dbt-adapter/                 # (future)
```

The `core` package contains the canonical model, shared resolver, and CLI. Adapters are separate packages that depend on core.

## Running Tests

```bash
# All tests across all packages
uv run pytest

# Core package only
uv run pytest packages/core/tests/

# Specific test file
uv run pytest packages/core/tests/test_resolved_model.py -v

# With coverage
uv run pytest --cov=osi_core --cov-report=html

# Update snapshot tests
uv run pytest --snapshot-update
```

## Linting & Type Checking

```bash
# Ruff (linter + formatter)
uv run ruff check packages/core/src/

# Auto-fix
uv run ruff check packages/core/src/ --fix

# Pyright (type checker)
uv run pyright packages/core/src/
```

## CLI Commands

```bash
# Validate an OSI file (checks YAML + OSI schema)
semetric validate metrics.yaml --format osi

# Translate between formats (full pipeline: parse → resolve → translate)
semetric translate metrics.yaml --from osi --to snowflake

# Translate with specific version
semetric translate metrics.yaml --from osi --to snowflake --output-version 1.0

# Migrate spec version
semetric migrate old.yaml --from 0.1.1 --to 0.2.0 --output migrated.yaml

# Diff two files
semetric diff old.yaml new.yaml

# List available adapters
semetric adapters list
```

---

## Adding a New Adapter

### 1. Create Package Structure

```
packages/
├── myformat-adapter/
│   ├── src/osi_myformat_adapter/
│   │   ├── __init__.py
│   │   ├── adapter.py          # Main adapter class
│   │   └── py.typed             # PEP 561 marker
│   ├── tests/
│   │   ├── fixtures/
│   │   │   └── sample.yaml      # Example MyFormat file
│   │   └── test_adapter.py
│   ├── pyproject.toml
│   └── README.md
```

### 2. Define the Adapter Class

```python
# adapter.py
from pathlib import Path
from typing import Union, Optional, List, Dict, Any
from osi_core.models import (
    ResolvedModel,
    ParseResult,
    DialectExpression,
    DialectExpr,
    Dialect,
    CustomExtension,
    Vendor,
)
from osi_core.resolver import resolve


class MyFormatAdapter:
    """Adapter for MyFormat semantic model YAML."""

    format_name = "myformat"

    def parse(
        self, source: Union[Path, str], version: Optional[str] = None
    ) -> ParseResult:
        """Parse MyFormat YAML into a ParseResult."""
        if isinstance(source, Path):
            with open(source) as f:
                raw = yaml.safe_load(f)
        else:
            raw = yaml.safe_load(source)

        # Detect version from file content if not provided
        source_version = version or self._detect_version(raw)

        # Extract custom_extensions for fields not in OSI spec
        custom_extensions = self._extract_extensions(raw)

        return ParseResult(
            raw=raw,
            source_format=self.format_name,
            source_version=source_version,
            custom_extensions=custom_extensions,
            osi_spec_version="0.1.1",
        )

    def translate(
        self, model: ResolvedModel, target_version: Optional[str] = None
    ) -> str:
        """Write ResolvedModel to MyFormat YAML."""
        data = {
            "semantic_model": [],
        }

        for sm in model.semantic_models:
            sm_data = {
                "name": sm.name,
                "datasets": [],
                "relationships": [],
                "metrics": [],
            }

            # Map datasets
            for ds in sm.datasets:
                ds_data = {
                    "name": ds.name,
                    "source": ds.source,
                    "fields": [],
                }
                if ds.primary_key:
                    ds_data["primary_key"] = ds.primary_key
                for f in ds.fields:
                    expr = self._select_dialect(f.expression, Dialect.ANSI_SQL)
                    ds_data["fields"].append({
                        "name": f.name,
                        "expression": expr,
                    })
                sm_data["datasets"].append(ds_data)

            # Map relationships
            for rel in sm.relationships:
                sm_data["relationships"].append({
                    "name": rel.name,
                    "from": rel.from_dataset,
                    "to": rel.to_dataset,
                    "from_columns": rel.from_columns,
                    "to_columns": rel.to_columns,
                })

            # Map metrics
            for m in sm.metrics:
                expr = self._select_dialect(m.expression, Dialect.ANSI_SQL)
                sm_data["metrics"].append({
                    "name": m.name,
                    "expression": expr,
                })

            data["semantic_model"].append(sm_data)

        # Apply custom_extensions for this platform
        data = self._apply_extensions(data, model)

        return yaml.dump(data, default_flow_style=False)

    # --- private helpers ---

    def _detect_version(self, raw: Dict[str, Any]) -> str:
        """Detect format version from file structure."""
        # Override with format-specific detection
        return "1.0"

    def _extract_extensions(self, raw: Dict[str, Any]) -> List[CustomExtension]:
        """Extract platform-specific fields into custom_extensions."""
        # Override: map platform fields not in OSI to CustomExtension
        return []

    def _apply_extensions(
        self, data: Dict[str, Any], model: ResolvedModel
    ) -> Dict[str, Any]:
        """Apply custom_extensions for this adapter's vendor."""
        # Override: extract extensions with matching vendor_name and apply
        return data

    @staticmethod
    def _select_dialect(
        expr: DialectExpression, fallback: Dialect
    ) -> str:
        """Select the best expression string for the target dialect."""
        if not expr.dialects:
            return ""
        for de in expr.dialects:
            if de.dialect == fallback:
                return de.expression
        # Fall back to first available
        return expr.dialects[0].expression
```

### 3. Package Configuration

```toml
# pyproject.toml
[project]
name = "osi-myformat-adapter"
version = "0.1.0"
description = "MyFormat adapter for osi-core"
requires-python = ">=3.12"
dependencies = [
    "osi-core>=0.1.0",
    "pyyaml>=6.0",
]

[project.entry-points."osi.adapters"]
myformat = "osi_myformat_adapter:adapter"

[build-system]
requires = ["uv_build>=0.11"]
build-backend = "uv_build"
```

### 4. Register in Root Workspace

```toml
# pyproject.toml (root)
[tool.uv]
workspace = [
    "packages/core",
    "packages/osi-adapter",
    "packages/myformat-adapter",  # Add this
]
```

### 5. Write Tests

```python
# tests/test_adapter.py
from pathlib import Path
import yaml
from osi_myformat_adapter import adapter as myformat_adapter


class TestMyFormatAdapter:
    @pytest.fixture
    def sample_file(self) -> Path:
        return Path(__file__).parent / "fixtures" / "sample.yaml"

    @pytest.fixture
    def sample_parse_result(self, sample_file) -> ParseResult:
        return myformat_adapter.MyFormatAdapter().parse(sample_file)

    def test_parse_produces_valid_parse_result(self, sample_file):
        result = myformat_adapter.MyFormatAdapter().parse(sample_file)
        assert result.source_format == "myformat"
        assert result.raw is not None

    def test_parse_preserves_extensions(self, sample_file):
        result = myformat_adapter.MyFormatAdapter().parse(sample_file)
        # Verify platform-specific fields survived as extensions
        assert len(result.custom_extensions) >= 0

    def test_resolve_produces_valid_model(self, sample_parse_result):
        from osi_core.resolver import resolve
        model = resolve(sample_parse_result)
        assert model.osi_spec_version == "0.1.1"
        assert len(model.semantic_models) > 0

    def test_roundtrip(self, sample_file, tmp_path):
        from osi_core.resolver import resolve

        a = myformat_adapter.MyFormatAdapter()

        # parse → resolve → translate
        result = a.parse(sample_file)
        model = resolve(result)
        output = a.translate(model)

        # Should be valid YAML
        reloaded = yaml.safe_load(output)
        assert "semantic_model" in reloaded
```

### 6. Create Test Fixture

```yaml
# tests/fixtures/sample.yaml
# A representative MyFormat semantic model YAML file
# Use real field names and structure from the platform spec
semantic_model:
  - name: sales_analytics
    description: Sales and customer analytics model
    datasets:
      - name: orders
        source: sales.public.orders
        primary_key: [order_id]
        fields:
          - name: order_id
            expression:
              dialects:
                - dialect: ANSI_SQL
                  expression: order_id
          - name: amount
            expression:
              dialects:
                - dialect: ANSI_SQL
                  expression: amount
    metrics:
      - name: total_revenue
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: SUM(orders.amount)
```

---

## Resolver Contract

The shared resolver is called after `adapter.parse()` and before `adapter.translate()`. Adapters never call the resolver directly — the `Translator` orchestrates it. The resolver receives a `ParseResult` and returns a `ResolvedModel`.

```python
from osi_core.resolver import resolve

parse_result: ParseResult
model: ResolvedModel = resolve(parse_result)
```

The resolver handles:
- Mapping platform types to OSI types
- Type normalization (e.g., string → dialect enum)
- Dialect selection (prefer platform-native, fall back to ANSI_SQL)
- Populating `custom_extensions` at every level
- Tracking `osi_spec_version` from `ParseResult`

If an adapter needs custom normalization logic beyond what the shared resolver provides, it can subclass or wrap the resolver internally. Document the deviation clearly.

---

## Common Patterns

### Dialect Selection

When a field or metric has multiple dialect expressions, select the best one:

```python
# Prefer the adapter's target dialect, fall back to ANSI_SQL
PREFERRED_DIALECT = Dialect.ANSI_SQL  # or adapter-specific dialect

def select_dialect(expr: DialectExpression) -> str:
    for de in expr.dialects:
        if de.dialect == PREFERRED_DIALECT:
            return de.expression
    # Fall back to ANSI_SQL
    for de in expr.dialects:
        if de.dialect == Dialect.ANSI_SQL:
            return de.expression
    # Last resort: first available
    return expr.dialects[0].expression
```

### Composite Key Relationships

OSI uses arrays for composite keys:

```yaml
from_columns: [product_id, variant_id]
to_columns: [id, variant_id]
```

Both arrays must have the same length. The order matters — it's positional correspondence.

### Custom Extension Preservation

On read: map non-OSI fields to `CustomExtension`:

```python
def _extract_extensions(self, raw: Dict) -> List[CustomExtension]:
    extensions = []
    # Example: platform-specific warehouse config
    if "warehouse" in raw:
        extensions.append(CustomExtension(
            vendor_name=Vendor.SNOWFLAKE,
            data=json.dumps({"warehouse": raw["warehouse"]}),
        ))
    return extensions
```

On write: apply extensions with matching `vendor_name`:

```python
def _apply_extensions(self, data: Dict, model: ResolvedModel) -> Dict:
    for ext in model.custom_extensions:
        if ext.vendor_name == Vendor.SNOWFLAKE:
            config = json.loads(ext.data)
            data["warehouse"] = config.get("warehouse")
    return data
```

---

## Common Pitfalls

1. **Missing newline at EOF**: Ruff enforces `W292`. Add `\n` at end of file.
2. **Discarding non-OSI fields**: Always extract into `custom_extensions` — never lose platform data silently.
3. **Forgetting dialect fallback**: When writing, if the target dialect isn't in the expression, log a warning and fall back to ANSI_SQL.
4. **Not registering entry point**: The adapter won't be discovered without the `[project.entry-points."osi.adapters"]` section in its `pyproject.toml`.
5. **Versioning adapter vs. format**: Adapter version is for the adapter package itself, not the platform format version. Format version is tracked per-file via `source_version`.

---

## Resources

- [OSI Core Spec](https://github.com/open-semantic-interchange/OSI/blob/main/core-spec/spec.md)
- [OSI JSON Schema](https://github.com/open-semantic-interchange/OSI/blob/main/core-spec/osi-schema.json)
- [OSI Converters](https://github.com/open-semantic-interchange/OSI/tree/main/converters)
- [Pydantic v2 Docs](https://docs.pydantic.dev/)
- [sqlglot](https://github.com/tobymao/sqlglot) (for future expression validation)
