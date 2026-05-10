# Adapter Package Specification

This document defines the contract and conventions for osi-core adapter packages.

---

## What is an Adapter?

An adapter translates between a platform's semantic model format and the OSI-aligned canonical model. Each adapter is an independent Python package with its own version number.

Adapters live in `packages/<name>-adapter/` in the monorepo and are published to PyPI independently.

---

## Contract

Every adapter must expose a single class — the adapter instance — via the `osi.adapters` entry point:

```python
# pyproject.toml of the adapter package
[project.entry-points."osi.adapters"]
myformat = "osi_myformat_adapter:MyFormatAdapter"
```

The adapter class must implement:

```python
class BaseAdapter(ABC):
    format_name: str   # lowercase, used in CLI: --from osi, --to snowflake

    def parse(
        self, source: Union[Path, str], version: Optional[str] = None
    ) -> ParseResult:
        """
        Parse platform YAML → ParseResult.
        Must be lenient: accept any version of the platform format.
        Extract platform-specific fields into custom_extensions.
        """
        ...

    def translate(
        self, model: ResolvedModel, target_version: Optional[str] = None
    ) -> str:
        """
        Write ResolvedModel → platform YAML.
        Apply custom_extensions for this platform.
        Default to current platform spec. Use target_version for older formats.
        """
        ...
```

The `Translator` in core calls these methods and injects the shared resolver between them:

```
adapter.parse(source) → ParseResult
resolve(ParseResult)   → ResolvedModel  (core, shared)
adapter.translate(model) → str
```

---

## Adapter Lifecycle

### Installing an Adapter

```bash
pip install osi-snowflake-adapter
```

Core discovers it at runtime via entry points. No changes to core needed.

### Versioning

Adapter version ≠ platform format version.

| Version | What it tracks |
|---------|---------------|
| Adapter package version (`0.1.0`) | The adapter code itself (semver) |
| `ParseResult.source_version` | The platform format version from the input file |
| `ResolvedModel.osi_spec_version` | The OSI spec version from the input file |

When the platform format changes (e.g., Snowflake v2 API), publish adapter `0.2.0` that handles both v1 and v2. `source_version` on the parsed model tells which format was read.

When the OSI spec evolves, update core's `Resolver`. All adapters benefit without releasing new adapter versions.

### Release Checklist

Before publishing an adapter:

- [ ] Entry point registered in `pyproject.toml` under `[project.entry-points."osi.adapters"]`
- [ ] `dependencies` includes `semetric-core>=<version>`
- [ ] Tests pass: `uv run pytest packages/<name>-adapter/`
- [ ] Roundtrip test: parse → resolve → translate → parse → resolve → compare
- [ ] Version bumped (if code changed): `bump2version` or manual update in `pyproject.toml`
- [ ] CHANGELOG.md updated

---

## Package Structure

```
packages/<name>-adapter/
├── src/osi_<name>_adapter/
│   ├── __init__.py          # exports the adapter class
│   └── adapter.py           # adapter implementation
├── tests/
│   ├── fixtures/
│   │   ├── sample.yaml      # primary test fixture (OSI-aligned)
│   │   ├── legacy.yaml      # older format version for compat tests
│   │   └── extensions.yaml  # file with custom_extensions for roundtrip test
│   ├── test_adapter.py
│   └── test_roundtrip.py
├── pyproject.toml
├── README.md
└── CHANGELOG.md
```

The fixture files are OSI-aligned (not platform-native) unless specifically testing legacy format parsing. The roundtrip test parses the OSI fixture, resolves, and writes — verifying the adapter can both read OSI-aligned input and produce valid output.

---

## Testing Requirements

### Required Tests

#### 1. Parse Result Integrity
```python
def test_parse_produces_valid_parse_result(sample_file):
    result = adapter.parse(sample_file)
    assert result.source_format == adapter.format_name
    assert result.raw is not None
    assert result.osi_spec_version == "0.1.1"
```

#### 2. Extension Preservation
```python
def test_parse_preserves_custom_extensions():
    result = adapter.parse(fixtures / "extensions.yaml")
    # Platform-specific fields were extracted into custom_extensions
    assert any(e.vendor_name == Vendor.MYFORMAT for e in result.custom_extensions)
```

#### 3. Resolve Produces Valid Model
```python
def test_resolve_produces_valid_osi_model(sample_parse_result):
    model = resolve(sample_parse_result)
    assert model.osi_spec_version == "0.1.1"
    assert len(model.semantic_models) > 0
```

#### 4. Roundtrip Fidelity
```python
def test_roundtrip(sample_file):
    result1 = adapter.parse(sample_file)
    model = resolve(result1)
    output = adapter.translate(model)
    result2 = adapter.parse(output)  # Re-parse the written output
    model2 = resolve(result2)
    # Core fields preserved
    assert model.semantic_models[0].name == model2.semantic_models[0].name
```

#### 5. Translate Produces Valid YAML
```python
def test_translate_produces_valid_yaml(sample_parse_result):
    model = resolve(sample_parse_result)
    output = adapter.translate(model)
    data = yaml.safe_load(output)
    assert "semantic_model" in data  # or equivalent top-level key
```

#### 6. Version Handling
```python
def test_parse_detects_version_from_file(sample_file):
    result = adapter.parse(sample_file)
    assert result.source_version is not None

def test_translate_with_target_version(sample_parse_result):
    model = resolve(sample_parse_result)
    output = adapter.translate(model, target_version="1.0")
    # Should produce valid output at target version
```

---

## Compatibility Testing

When a platform format evolves, add a legacy fixture and test:

```python
def test_parse_legacy_format():
    result = adapter.parse(fixtures / "legacy.yaml")
    assert result.source_version == "legacy"
    model = resolve(result)
    # Should normalize correctly
    assert model.semantic_models[0].datasets[0].name is not None
```

The adapter should handle **at least two** format versions simultaneously:
1. Current (latest platform format)
2. Previous (legacy, for backward compatibility)

If the platform format changes significantly, release a new adapter major version and document the migration path.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid YAML | Wrap `yaml.YAMLError` in `ValueError("Invalid YAML: {e}")` |
| Missing required fields | Raise `ValueError` with the specific field name |
| Unknown version | Log warning, parse with current version as fallback |
| Missing custom extension | Silently skip (don't fail if extension not present) |
| Dialect not available | Log warning, fall back to ANSI_SQL |

Adapters should not catch `pydantic.ValidationError` from the resolver — let it propagate. If the resolver produces an invalid model, that's a bug in the resolver, not the adapter.

---

## Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Package name | `osi-<name>-adapter` | `osi-snowflake-adapter` |
| Module import | `osi_<name>_adapter` | `osi_snowflake_adapter` |
| Entry point | `<name>` | `snowflake` |
| CLI format name | lowercase, no spaces | `--from snowflake` |
| Class name | `<Name>Adapter` | `SnowflakeAdapter` |
| Version | semver | `0.1.0`, `1.0.0` |

---

## Built-in Adapters

| Adapter | Package | Status |
|---------|---------|--------|
| OSI | `packages/osi-adapter/` | Planned (refactor from core readers/writers) |
| MetricFlow | `packages/metricflow-adapter/` | Planned (extract from core) |
| Snowflake | `packages/snowflake-adapter/` | Future |
| dbt | `packages/dbt-adapter/` | Future |
| Databricks | `packages/databricks-adapter/` | Future |
