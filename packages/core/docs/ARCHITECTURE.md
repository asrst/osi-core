# OSI Core Architecture

## Core Principles

### 1. Canonical Model = OSI Spec

**Decision**: `ResolvedModel` mirrors the OSI Core Metadata Specification exactly. OSI spec versions are the canonical model versions.

**Why**:
- One source of truth for the data model
- All adapters map to/from the same canonical form
- Spec version = model version — no mental overhead tracking two version numbers
- OSI spec is an open standard maintained independently; semetric benefits from that work

**Trade-off**: `ResolvedModel` is tightly coupled to the OSI spec. If OSI evolves, semetric may need to update the canonical model. The `osi_spec_version` field on `ResolvedModel` tracks which spec version a file was written against.

### 2. Three-Stage Pipeline

**Decision**: Every translation flows through three distinct stages:

```
Platform YAML
    │
    ▼
┌─────────────┐
│   Parser    │  adapter.parse(source) → ParseResult
│  (adapter)  │  Handles: format detection, lenient read, version extraction,
└──────┬──────┘  raw platform-native dict, custom extension extraction
       │ ParseResult { raw, source_format, source_version, custom_extensions }
       ▼
┌─────────────┐
│   Resolver  │  resolve(ParseResult) → ResolvedModel
│   (core)    │  Maps platform-native → OSI-aligned canonical model
└──────┬─────┘  Handles: type normalization, dialect selection, extension mapping
       │ ResolvedModel (OSI-aligned, osi_spec_version tracked)
       ▼
┌─────────────┐
│   Adapter   │  adapter.translate(model, target_version?) → Platform YAML
│  (adapter)  │  Handles: dialect selection for target, extension application
└─────────────┘
```

**Why**:
- **Parser** (per-adapter): Handles format quirks, version detection, and preserving platform-specific data that doesn't map to OSI
- **Resolver** (shared, in core): Does the normalization work once. All adapters benefit from OSI spec updates without touching their parsers
- **Translator** (core): Orchestrates the pipeline and handles adapter discovery

**Not OSI-centric**: The pipeline is format-agnostic. Every adapter — OSI, MetricFlow, Snowflake, dbt — goes through the same stages. Only the parser and writer are platform-specific.

### 3. Lenient Parse, Strict Resolve

**Decision**: Parsers accept any version of their platform format. The shared Resolver normalizes to the current OSI spec.

**Why**:
- Readers don't need versioned branches (no `read_v1()`, `read_v2()` per adapter)
- New platform versions are handled by updating the parser only
- The canonical model is always in current spec form
- `osi_spec_version` is tracked for auditability

**Trade-off**: When writing back, old platform versions can only be emitted via `--output-version` flag. Silent auto-upgrade means old files re-saved in their original format is not the default.

### 4. Adapter = Separate Package

**Decision**: Each format adapter is an independent Python package.

**Why**:
- When Snowflake changes their format, only `snowflake-adapter` needs a release — no changes to core or other adapters
- Independent versioning: `osi-adapter v1.2` while `snowflake-adapter v0.8`
- Each adapter can be tested and released on its own schedule
- Community can contribute adapters without touching core

**Structure**: All adapters live in `packages/` in the monorepo but are published as independent PyPI packages. Shared CI tooling in root `pyproject.toml`.

### 5. Preserved Extensions, Not Discarded

**Decision**: Platform-specific metadata that has no OSI equivalent is stored in `custom_extensions` at every level and preserved through round-trips.

**Why**:
- Never lose data silently when converting between formats
- `custom_extensions` with `vendor_name` matching the target platform are applied on write
- Extensions for other platforms are preserved — a single OSI file can carry metadata for Snowflake, dbt, and Databricks simultaneously

---

## Data Flow

### Pipeline Stages

#### 1. Parser (per adapter)

```python
class Adapter:
    def parse(self, source: Union[Path, str], version: Optional[str] = None) -> ParseResult:
        """
        Leniently parse platform YAML into a raw dict.
        Detect source version from file content or explicit arg.
        Extract platform-specific fields into custom_extensions.
        """
```

**Responsibilities**:
- Accept any version of the platform format
- Detect `source_version` from file structure or explicit parameter
- Return raw platform-native dict (unmodified)
- Extract `custom_extensions` for fields that don't map to OSI
- Validate basic YAML structure (but not OSI conformance)

**Output**: `ParseResult`

```python
@dataclass
class ParseResult:
    raw: dict                                  # platform-native dict
    source_format: str                         # e.g., "snowflake_semantic"
    source_version: str                        # e.g., "2.0", "legacy"
    custom_extensions: List[CustomExtension]   # preserved for round-trip
    osi_spec_version: str                      # OSI spec version of source
```

#### 2. Resolver (shared, in core)

```python
def resolve(parse_result: ParseResult) -> ResolvedModel:
    """
    Map platform-native dict to OSI-aligned ResolvedModel.
    Apply type normalization, dialect selection.
    Preserve custom_extensions on the canonical model.
    """
```

**Responsibilities**:
- Map platform types to OSI types
- Select appropriate SQL dialect for multi-dialect expressions (prefer platform-native dialect, fall back to ANSI_SQL)
- Populate all OSI fields from platform dict
- Preserve `custom_extensions` at every level
- Track `osi_spec_version` from `ParseResult`

**Input**: `ParseResult`
**Output**: `ResolvedModel`

#### 3. Adapter.translate (per adapter)

```python
class Adapter:
    def translate(
        self,
        model: ResolvedModel,
        target_version: Optional[str] = None
    ) -> str:
        """
        Convert ResolvedModel to platform YAML.
        Apply custom_extensions for this platform.
        Select dialect for multi-dialect expressions.
        Optionally emit older spec version via target_version.
        """
```

**Responsibilities**:
- Map OSI fields to platform format
- Extract `custom_extensions` where `vendor_name` matches this platform and apply
- Select the appropriate SQL dialect for expressions
- Default to current spec on write; support `--output-version` for older formats

### Translator Orchestration

The `Translator` class in core wires the stages together:

```python
class Translator:
    def __init__(self, adapters: Mapping[str, "Adapter"]):
        self.adapters = adapters

    def translate(
        self,
        source: Union[Path, str],
        from_format: str,
        to_format: str,
        input_version: Optional[str] = None,
        output_version: Optional[str] = None,
    ) -> str:
        """Full pipeline: parse → resolve → translate."""
        adapter = self.adapters[from_format]
        parse_result = adapter.parse(source, input_version)
        model = resolve(parse_result)
        out_adapter = self.adapters[to_format]
        return out_adapter.translate(model, output_version)
```

---

## Data Model

### ResolvedModel (OSI-aligned)

The canonical model matches the OSI Core Metadata Specification v0.1.1:

```python
class ResolvedModel(BaseModel):
    osi_spec_version: str = "0.1.1"
    name: str
    description: Optional[str] = None
    semantic_models: List["SemanticModel"] = []
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class SemanticModel(BaseModel):
    name: str
    description: Optional[str] = None
    datasets: List[Dataset] = []
    relationships: List[Relationship] = []
    metrics: List[Metric] = []
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class Dataset(BaseModel):
    name: str
    source: str                                  # e.g., database.schema.table
    primary_key: List[str] = []                  # single or composite
    unique_keys: List[List[str]] = []            # multiple unique key defs
    description: Optional[str] = None
    fields: List[Field] = []
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class Field(BaseModel):
    name: str
    expression: DialectExpression                 # multi-dialect SQL
    dimension: Optional[Dimension] = None        # includes is_time
    label: Optional[str] = None
    description: Optional[str] = None
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class DialectExpression(BaseModel):
    dialects: List[DialectExpr]                  # one per supported dialect


class DialectExpr(BaseModel):
    dialect: Dialect                             # ANSI_SQL, SNOWFLAKE, etc.
    expression: str                              # SQL expression string


class Dimension(BaseModel):
    is_time: bool = False


class Relationship(BaseModel):
    name: str
    from_dataset: str
    to_dataset: str
    from_columns: List[str] = []                 # supports composite keys
    to_columns: List[str] = []                   # same cardinality as from_columns
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class Metric(BaseModel):
    name: str
    expression: DialectExpression               # multi-dialect aggregate expression
    description: Optional[str] = None
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class CustomExtension(BaseModel):
    vendor_name: Vendor                          # SNOWFLAKE, DBT, etc.
    data: str                                    # JSON string


class AIContext(BaseModel):
    instructions: Optional[str] = None
    synonyms: List[str] = []
    examples: List[str] = []
```

### Enums

```python
class Dialect(Enum):
    ANSI_SQL = "ANSI_SQL"
    SNOWFLAKE = "SNOWFLAKE"
    MDX = "MDX"
    TABLEAU = "TABLEAU"
    DATABRICKS = "DATABRICKS"
    MAQL = "MAQL"


class Vendor(Enum):
    COMMON = "COMMON"
    SNOWFLAKE = "SNOWFLAKE"
    SALESFORCE = "SALESFORCE"
    DBT = "DBT"
    DATABRICKS = "DATABRICKS"
    GOODDATA = "GOODDATA"
```

### Why String Expressions (Not AST)

Expressions are stored as strings, not parsed ASTs:

- **Neutral**: Works across SQL dialects without committing to one
- **No execution**: sqlglot is AST-only — no security risk from untrusted input
- **Debuggable**: Raw SQL is human-readable; can parse with sqlglot for validation if needed
- **Simple**: Dialect selection is string-level; we pick the right string per dialect

If validation is needed, `sqlglot` can parse the selected dialect expression without needing to represent it as a structured type in the model.

---

## Extension Architecture

### Adapter Discovery

Adapters are discovered via Python entry points:

```toml
# adapter's pyproject.toml
[project.entry-points."osi.adapters"]
snowflake = "semetric_snowflake_adapter:adapter"
osi = "semetric_osi_adapter:adapter"
metricflow = "semetric_metricflow_adapter:adapter"
```

Core discovers adapters at startup:

```python
def discover_adapters() -> Dict[str, Adapter]:
    adapters = {}
    for ep in importlib.metadata.entry_points(group="osi.adapters"):
        adapters[ep.name] = ep.load()()
    return adapters
```

Third-party adapters can be installed as pip packages without modifying core.

### Entry Point vs. Separate Reader/Writer

Previous design used separate `semetric.readers` and `semetric.writers` entry points. The current design uses a single `Adapter` class that owns both `parse()` and `translate()`. This keeps parse/translate logic together — an adapter understands its own format deeply enough to handle both directions without a shared abstraction leaking platform-specific concerns.

---

## Error Handling

| Error | Source | Response |
|-------|--------|----------|
| File not found | Parser | `FileNotFoundError` |
| Invalid YAML | Parser | `yaml.YAMLError` (wrapped) |
| Platform format error | Parser | `ValueError` with descriptive message |
| OSI schema violation | Resolver | `pydantic.ValidationError` |
| Unsupported adapter | Translator | `KeyError` |
| Missing dialect | Writer | Log warning, fall back to ANSI_SQL |

CLI exits: 0 = success, 1 = usage/validation error, 2 = system error.

---

## Security

1. **YAML**: Always `yaml.safe_load()` — no code execution from untrusted files
2. **SQL Expressions**: Stored as strings, not executed; sqlglot is AST-only
3. **File I/O**: `Path` operations via pathlib — prevents directory traversal
4. **Custom Extensions**: `data` field is a JSON string parsed on read; no arbitrary execution

---

## Multi-Model Files

OSI spec allows `semantic_model[]` as an array (multiple models in one YAML file). The canonical model (`ResolvedModel`) holds this array directly. The CLI operates on the whole file. A `--model <name>` flag selects a single named model for operations that need it.

```bash
# Operate on all models in the file
semetric validate metrics.yaml

# Operate on a specific model
semetric translate metrics.yaml --model sales_analytics --to-format snowflake
```

Future: `resolve_to_files()` utility to split a multi-model file into one `ResolvedModel` per file.
