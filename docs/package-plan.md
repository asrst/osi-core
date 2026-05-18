
## 1. Understanding the OSI Repository's True Structure

The repository is organized into five functional areas, each with a distinct role:

```
OSI/
├── core-spec/                    # THE CANONICAL SPEC
│   ├── spec.md                   # Human-readable specification (v0.1.1)
│   ├── spec.yaml                 # Machine-readable spec (enums, structures)
│   └── osi-schema.json           # JSON Schema Draft 2020-12 for validation
├── converters/                   # Reference implementations (4 vendors)
│   ├── index.md                  # Hub-and-spoke architecture documentation
│   ├── snowflake/                # Python: OSI ↔ Snowflake Cortex Analyst YAML
│   ├── gooddata/                 # Python: OSI ↔ GoodData declarative LDM JSON
│   ├── salesforce/               # Java: OSI ↔ Salesforce DMO JSON
│   └── polaris/                  # Java: OSI ↔ Apache Polaris (Iceberg REST Catalog)
├── validation/
│   └── validate.py               # Multi-layer validator (JSON Schema + uniqueness + refs + SQL)
├── examples/
│   └── tpcds_semantic_model.yaml # Complete reference OSI model (TPC-DS retail benchmark)
└── docs/                         # Governance and community docs
```

**The spec** defines the canonical OSI model: version, semantic_model array, datasets, fields, relationships, metrics, custom_extensions, and ai_context. It enumerates supported dialects (ANSI_SQL, SNOWFLAKE, MDX, TABLEAU, DATABRICKS, MAQL) and vendors (COMMON, SNOWFLAKE, SALESFORCE, DBT, DATABRICKS, GOODDATA). The validation script enforces all of this plus uniqueness constraints and SQL syntax checks.

**The converters** follow a hub-and-spoke architecture where OSI is the hub. Each converter is a spoke handling two directions: import (Vendor → OSI) and export (OSI → Vendor).

---

## 2. Phase 1: Python Converters — What Already Exists

### 2.1 Snowflake Converter (converters/snowflake/)

**Structure:**
```
converters/snowflake/
├── README.md
├── requirements.txt          # PyYAML dependency
├── src/
│   └── osi_to_snowflake_yaml_converter.py   # Single-file converter (169 lines)
└── tests/
    ├── test_osi_to_snowflake_yaml_converter.py   # 327 lines of tests
    └── example_converted_tpcds_semantic_model.yaml  # Expected output fixture
```

**Current state:** Unidirectional only (OSI → Snowflake). The `convert_osi_to_snowflake()` function parses OSI YAML, validates the version, and maps OSI constructs to Snowflake Cortex Analyst semantic model YAML. It handles datasets→tables, relationships, metrics, and multi-dialect SQL selection (preferring Snowflake dialect, falling back to ANSI_SQL).

**Key internal functions:**
- `_convert_model()` — Top-level: name, description, tables, relationships, metrics
- `_convert_dataset()` — Maps OSI dataset fields to Snowflake table dimensions/measures
- `_convert_relationship()` — Foreign key relationships
- `_convert_named_expr()` — Metrics with dialect-aware SQL extraction
- `_parse_source()` — Parses `db.schema.table` into database/schema/table
- `_normalize_identifier()` — Uppercases unquoted identifiers
- `_classify_field()` — Determines if a field is a dimension or measure
- `_extract_expression()` — Picks the best dialect from multi-dialect expressions
- `_extract_synonyms()` — Pulls AI context synonyms

**Tests:** 327 lines covering every internal function with edge cases: quoted identifiers, subqueries in source, composite primary keys, whitespace handling, error conditions.

**Limitations:** Import direction (Snowflake → OSI) is not implemented. No Snowflake-specific custom_extensions handling. ai_context on relationships is dropped (no native Snowflake equivalent).

### 2.2 GoodData Converter (converters/gooddata/)

**Structure:**
```
converters/gooddata/
├── README.md
├── pyproject.toml
├── src/gooddata_osi/
│   ├── __init__.py              # Exports gooddata_to_osi, osi_to_gooddata
│   ├── models.py                # Dataclasses for GoodData LDM + OSI structures (128 lines)
│   ├── gooddata_to_osi.py       # Import: GoodData → OSI (97 lines)
│   └── osi_to_gooddata.py       # Export: OSI → GoodData (144 lines)
└── tests/
    ├── __init__.py
    ├── conftest.py               # Shared fixtures (load JSON/YAML test data)
    ├── fixtures/
    │   ├── gooddata_tpcds.json   # Sample GoodData declarative model (TPC-DS)
    │   └── osi_tpcds.yaml        # Expected OSI output for the same model
    ├── test_gooddata_to_osi.py   # Import direction tests (82 lines)
    ├── test_osi_to_gooddata.py   # Export direction tests
    ├── test_roundtrip.py         # Bidirectional integrity tests (45 lines)
    └── test_models.py            # Dataclass model tests
```

**Current state:** Fully bidirectional. The GoodData converter is the most complete reference implementation in the repository. It:

- **Import (gooddata_to_osi.py):** Converts GoodData's declarative LDM (datasets, attributes, facts, references, date instances) into OSI semantic model format, preserving GoodData-specific metadata in `custom_extensions` and generating dual-dialect expressions (ANSI_SQL + MAQL).

- **Export (osi_to_gooddata.py):** Converts OSI back to GoodData format, reconstructing attributes, facts, labels, references, and date instances from OSI constructs. Handles MAQL expression parsing and reference resolution.

- **Models (models.py):** Defines Python dataclasses for every GoodData LDM entity (GdDataset, GdAttribute, GdFact, GdLabel, GdReference, GdDateInstance, etc.) with proper type annotations.

**Tests:** Four test files with fixtures-based testing. The roundtrip tests are particularly important—they verify GoodData → OSI → GoodData preserves dataset counts, attribute counts, fact counts, date instances, and reference targets.

**Limitations:** Metrics are not converted (GoodData uses MAQL with context-aware dimensionality; OSI metrics are SQL-expression-based). AggregatedFacts and workspace data filters are not yet supported.

---

## 3. Phase 2 Preview: Java Converters — What Exists

### 3.1 Salesforce Converter (converters/salesforce/)

**Structure:**
```
converters/salesforce/
├── pom.xml
├── src/main/java/org/osi/converter/salesforce/
│   ├── ConverterImpl.java        # Core mapping engine
│   ├── handlers/                 # Mapping handlers (DatasetMappingHandler, etc.)
│   └── models/                   # Java POJOs for Salesforce DMO and OSI
└── src/test/resources/examples/  # Test fixtures (JSON/YAML)
```

**Key characteristics:** Uses a configurable mapping pipeline with handler classes for each OSI construct. Dependencies: Jackson (JSON), SnakeYAML, json-schema-validator. No Salesforce SDK — pure format conversion.

### 3.2 Polaris Converter (converters/polaris/)

**Structure:**
```
converters/polaris/
├── pom.xml
├── src/main/java/org/osi/converter/polaris/
│   ├── PolarisClient.java        # REST client for Iceberg Catalog API
│   ├── PolarisToOsiConverter.java # Import logic
│   └── OsiToPolarisConverter.java # Export logic
└── src/test/java/org/osi/converter/polaris/  # JUnit tests
```

**Key characteristics:** Unlike the other converters, the Polaris converter includes a real HTTP client that communicates with Apache Polaris's implementation of the Iceberg REST Catalog API (OAuth2 authentication, listing namespaces/tables). This is the only converter that blurs the line between "converter" and "connector."

---

## 4. The Target `osi-core` Architecture

Based on the patterns in the existing converters, here is the target structure for `osi-core`:

```
osi-core/
├── pyproject.toml
├── README.md
├── LICENSE                          # Apache 2.0
├── src/osi_core/
│   ├── __init__.py                  # Version, public API exports
│   │
│   ├── models.py                    # Pydantic models for all OSI constructs
│   │                                # (SemanticModel, Dataset, Field, Relationship,
│   │                                #  Metric, Expression, DialectExpression,
│   │                                #  CustomExtension, AIContext, Dimension)
│   │
│   ├── validator.py                 # Multi-layer validation (wraps validate.py logic)
│   │   ├── validate_schema()        #   JSON Schema validation
│   │   ├── validate_unique_names()  #   Duplicate detection
│   │   ├── validate_references()    #   Referential integrity
│   │   └── validate_sql()           #   SQL syntax via sqlglot
│   │
│   ├── serializer.py                # YAML/JSON load/dump with built-in validation
│   │   ├── load_osi_yaml()          #   Parse + validate in one call
│   │   ├── dump_osi_yaml()          #   Serialize OSI model to YAML
│   │   └── load_osi_json()          #   Parse JSON OSI variant
│   │
│   ├── converters/
│   │   ├── __init__.py              # Converter registry
│   │   ├── base.py                  # Abstract BaseConverter class
│   │   │   ├── BaseConverter.to_osi(native_model: dict) -> dict
│   │   │   └── BaseConverter.from_osi(osi_model: dict) -> dict
│   │   │
│   │   ├── snowflake/
│   │   │   ├── __init__.py          # Exports SnowflakeConverter
│   │   │   ├── importer.py          # Snowflake → OSI (NEW — not in existing repo)
│   │   │   ├── exporter.py          # OSI → Snowflake (refactored from existing)
│   │   │   └── config.py            # Snowflake-specific extension constants
│   │   │
│   │   ├── gooddata/
│   │   │   ├── __init__.py          # Exports GoodDataConverter
│   │   │   ├── models.py            # GoodData LDM dataclasses (ported from existing)
│   │   │   ├── importer.py          # GoodData → OSI (refactored from gooddata_to_osi.py)
│   │   │   ├── exporter.py          # OSI → GoodData (refactored from osi_to_gooddata.py)
│   │   │   └── maql_utils.py        # MAQL expression parsing helpers
│   │   │
│   │   └── ...                      # Future: dbt, Cube, LookML, Tableau, etc.
│   │
│   ├── normalizer.py                # Shared normalization utilities
│   │   ├── normalize_identifier()
│   │   ├── parse_source()
│   │   └── extract_expression()
│   │
│   └── dialects.py                  # Multi-dialect SQL mapping
│       ├── DIALECT_MAP              # OSI dialect → sqlglot dialect
│       └── select_dialect()         # Pick best dialect for a target
│
├── tests/
│   ├── conftest.py                  # Global fixtures (TPC-DS OSI model, etc.)
│   ├── fixtures/
│   │   ├── tpcds_semantic_model.yaml    # From OSI repo examples/
│   │   ├── snowflake_tpcds.yaml         # From existing snowflake tests
│   │   ├── gooddata_tpcds.json          # From existing gooddata tests
│   │   └── invalid_models/              # Deliberately broken OSI files for validator testing
│   ├── test_models.py               # Verify Pydantic models match JSON Schema
│   ├── test_validator.py            # All validation layers
│   ├── test_serializer.py           # Load/dump roundtrip tests
│   ├── test_normalizer.py           # Unit tests for shared utilities
│   ├── converters/
│   │   ├── test_base.py             # Contract tests for BaseConverter interface
│   │   ├── snowflake/
│   │   │   ├── test_importer.py     # Snowflake → OSI tests
│   │   │   ├── test_exporter.py     # OSI → Snowflake tests (ported + extended)
│   │   │   └── test_roundtrip.py    # Snowflake → OSI → Snowflake
│   │   └── gooddata/
│   │       ├── test_importer.py     # GoodData → OSI tests (ported)
│   │       ├── test_exporter.py     # OSI → GoodData tests (ported)
│   │       └── test_roundtrip.py    # GoodData → OSI → GoodData (ported)
│   └── integration/                 # Cross-converter tests (Phase 3)
│       └── test_cross_converter.py  # Snowflake → OSI → GoodData equivalence
│
└── examples/
    └── tpcds_semantic_model.yaml    # Copied from OSI repo for reference
```

---

## 5. Core Abstractions

### 5.1 BaseConverter Interface

Extracted from the patterns in both existing Python converters:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseConverter(ABC):
    """Abstract base for all OSI converters.
    
    Every converter must implement two directions:
    - to_osi(): Convert a vendor's native representation to OSI format
    - from_osi(): Convert an OSI model to the vendor's native representation
    """

    # Each converter identifies its vendor name (matches OSI Vendor enum)
    VENDOR_NAME: str

    @abstractmethod
    def to_osi(self, native_model: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Convert vendor-specific model → OSI semantic model dict."""
        ...

    @abstractmethod
    def from_osi(self, osi_model: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Convert OSI semantic model dict → vendor-specific model."""
        ...
```

This interface captures exactly what both existing converters do. The Snowflake converter is currently missing `to_osi()` (import direction); the GoodData converter implements both.

### 5.2 Pydantic Models (models.py)

Generated from `osi-schema.json`:

```python
from pydantic import BaseModel
from typing import Optional, List, Union, Literal

class DialectExpression(BaseModel):
    dialect: Literal["ANSI_SQL", "SNOWFLAKE", "MDX", "TABLEAU", "DATABRICKS", "MAQL"]
    expression: str

class Expression(BaseModel):
    dialects: List[DialectExpression]  # minItems: 1

class Dimension(BaseModel):
    is_time: bool = False

class AIContext(BaseModel):
    instructions: Optional[str] = None
    synonyms: Optional[List[str]] = None
    examples: Optional[List[str]] = None

class Field(BaseModel):
    name: str
    expression: Expression
    description: Optional[str] = None
    dimension: Optional[Dimension] = None
    ai_context: Optional[Union[str, AIContext]] = None

class CustomExtension(BaseModel):
    vendor_name: Literal["COMMON", "SNOWFLAKE", "SALESFORCE", "DBT", "DATABRICKS", "GOODDATA"]
    data: str  # JSON string

class Relationship(BaseModel):
    name: str
    from_: str  # aliased from "from" in YAML
    to: str
    from_columns: List[str]
    to_columns: List[str]

class Dataset(BaseModel):
    name: str
    source: Optional[str] = None
    primary_key: Optional[List[str]] = None
    unique_keys: Optional[List[List[str]]] = None
    fields: List[Field] = []
    description: Optional[str] = None
    ai_context: Optional[Union[str, AIContext]] = None
    custom_extensions: Optional[List[CustomExtension]] = None

class Metric(BaseModel):
    name: str
    expression: Expression
    description: Optional[str] = None
    ai_context: Optional[Union[str, AIContext]] = None

class SemanticModel(BaseModel):
    name: str
    datasets: List[Dataset] = []
    relationships: List[Relationship] = []
    metrics: List[Metric] = []
    description: Optional[str] = None
    ai_context: Optional[Union[str, AIContext]] = None
    custom_extensions: Optional[List[CustomExtension]] = None

class OSIModel(BaseModel):
    version: Literal["0.1.1"]
    semantic_model: List[SemanticModel]
```

---

## 6. Phase 1 Development Plan (Week-by-Week)

### Week 1: Foundation — `osi_core` Scaffolding

**Day 1-2: Project setup and models**
- Initialize the `osi-core` Python project with `pyproject.toml`
- Copy `osi-schema.json` from the OSI repo into `src/osi_core/`
- Implement `models.py` with Pydantic models (as specified above)
- Write `test_models.py`: load the TPC-DS example YAML, parse into Pydantic models, verify all fields populated correctly

**Day 3-4: Serializer and validator**
- Implement `serializer.py` with `load_osi_yaml()` and `dump_osi_yaml()`
- Implement `validator.py` by wrapping the logic from `validation/validate.py`: JSON Schema validation (using `jsonschema.Draft202012Validator`), unique name detection, relationship reference checking, and SQL syntax validation via `sqlglot`
- Write `test_validator.py`: test against valid TPC-DS model (should pass), then create deliberately broken models (missing version, duplicate dataset names, invalid relationship references, bad SQL syntax) and verify each error is caught
- Write `test_serializer.py`: load TPC-DS YAML → dump to YAML → load again → assert structural equivalence

**Day 5: Normalizer utilities and BaseConverter**
- Implement `normalizer.py` by extracting `_normalize_identifier`, `_parse_source`, and `_extract_expression` from the Snowflake converter into shared utilities
- Implement `converters/base.py` with the `BaseConverter` abstract class
- Write `test_normalizer.py`: port the existing Snowflake normalizer tests
- Write `test_base.py`: contract tests that any BaseConverter subclass must satisfy

**Milestone:** `osi-core` can load, validate, serialize, and deserialize any OSI-compliant YAML file. The abstract converter interface is defined.

### Week 2: Snowflake Converter Refactoring

**Day 1-2: Exporter (OSI → Snowflake)**
- Create `converters/snowflake/exporter.py` by refactoring the existing `osi_to_snowflake_yaml_converter.py`
- Split the monolithic `_convert_model()` into smaller, testable methods that match the BaseConverter interface
- Implement `SnowflakeConverter.from_osi()` as the public API
- Port all 327 lines of existing tests to `tests/converters/snowflake/test_exporter.py`, adapting them to use the new class-based API

**Day 3-4: Importer (Snowflake → OSI) — NEW**
- Create `converters/snowflake/importer.py` with `SnowflakeConverter.to_osi()`
- Parse Snowflake Cortex Analyst YAML (tables → datasets, dimensions/measures → fields, relationships)
- Handle Snowflake-specific constructs: fully-qualified table names → source, time dimensions → dimension.is_time, measure filters → metric expressions
- Write `test_importer.py` using the fixture `snowflake_tpcds.yaml` as input, verify it produces valid OSI that matches the TPC-DS reference

**Day 5: Roundtrip and edge cases**
- Write `test_roundtrip.py`: Snowflake → OSI → Snowflake, verify table count, dimension count, measure count, and relationship count are preserved
- Handle custom_extensions: embed Snowflake warehouse/database metadata
- Handle dropped fields (ai_context on relationships, unsupported constructs) with warnings

**Milestone:** SnowflakeConverter is fully bidirectional. All existing tests pass plus new import tests.

### Week 3: GoodData Converter Refactoring

**Day 1-2: Port models and importer**
- Port `converters/gooddata/src/gooddata_osi/models.py` into `converters/gooddata/models.py`
- Port `gooddata_to_osi.py` into `converters/gooddata/importer.py`, adapting to the BaseConverter interface
- Port all existing test fixtures and tests from `test_gooddata_to_osi.py`

**Day 3-4: Port exporter and roundtrip tests**
- Port `osi_to_gooddata.py` into `converters/gooddata/exporter.py`
- Port `test_osi_to_gooddata.py` and `test_roundtrip.py`
- Port `test_models.py` for GoodData dataclass validation

**Day 5: Integration and cleanup**
- Write shared converter contract tests: both SnowflakeConverter and GoodDataConverter must pass the same BaseConverter contract tests
- Verify that both converters produce OSI models that pass `osi_core.validator.validate_schema()`

**Milestone:** GoodDataConverter is fully integrated into `osi-core`. Two converters, one consistent interface.

### Week 4: CLI and Release

**Day 1-2: Unified CLI**
- Build an `osi` CLI (using `click` or `argparse`) that leverages the converter registry:
  ```bash
  osi convert snowflake import views.yaml -o model.osi.yaml
  osi convert snowflake export model.osi.yaml -o views.yaml
  osi validate model.osi.yaml
  osi convert gooddata import ldm.json -o model.osi.yaml
  osi convert gooddata export model.osi.yaml -o ldm.json
  ```

**Day 3-4: Documentation and packaging**
- Write comprehensive README with usage examples
- Write converter-specific documentation explaining mappings and limitations
- Configure PyPI publishing via GitHub Actions

**Day 5: First release**
- Tag `v0.1.0` and publish to PyPI

**Milestone:** `pip install osi-core` works. Two converters, CLI, validation, all tested.

---

## 7. Phase 2: Java Converters — Pre-Plan

### Phase 2a: Replicate in Python (Weeks 5-7)

Both Java converters are pure format converters (no Java-specific SDK dependencies), making Python ports straightforward:

**Salesforce Converter Python Port:**
- Parse Salesforce DMO JSON → OSI (and reverse)
- Map the handler-based pipeline to Python functions
- Use the same test fixtures from the Java converter's `src/test/resources/examples/`

**Polaris Converter Python Port:**
- The Polaris converter is actually a hybrid converter+connector (it includes a REST client)
- For `osi-core`: extract only the pure conversion logic (Polaris metadata → OSI mapping)
- The REST client portion (PolarisClient.java) belongs in the commercial `osi-connectors` layer

### Phase 2b: Conformance Test Suite

A shared test suite validates both Python ports produce identical OSI to the original Java converters:

```python
# tests/conformance/test_salesforce.py
def test_python_port_matches_java_output():
    """The Python Salesforce converter must produce identical OSI to the Java version."""
    java_output = load_yaml("fixtures/java_salesforce_to_osi_output.yaml")
    python_output = SalesforceConverter().to_osi(load_json("fixtures/salesforce_dmo.json"))
    assert python_output == java_output
```

---

## 8. Immediate TDD Starting Point (What to Write Right Now)

Here is the first concrete test to write, based directly on the existing OSI validation script and TPC-DS example:

```python
# tests/test_validator.py
import pytest
from pathlib import Path
from osi_core.serializer import load_osi_yaml
from osi_core.validator import validate_schema

FIXTURES = Path(__file__).parent / "fixtures"

def test_tpcds_example_passes_validation():
    """The TPC-DS example from the OSI repo must pass all validations."""
    model = load_osi_yaml(FIXTURES / "tpcds_semantic_model.yaml")
    errors = validate_schema(model)
    assert len(errors) == 0, f"TPC-DS example should be valid, got: {errors}"

def test_missing_version_detected():
    """A model without version must fail."""
    errors = validate_schema({"semantic_model": []})
    assert len(errors) > 0
    assert any("version" in e for e in errors)

def test_duplicate_dataset_names_detected():
    """Two datasets with the same name must fail."""
    model = {
        "version": "0.1.1",
        "semantic_model": [{
            "name": "test",
            "datasets": [
                {"name": "orders", "fields": []},
                {"name": "orders", "fields": []},  # duplicate!
            ]
        }]
    }
    errors = validate_schema(model)
    assert any("Duplicate" in e for e in errors)
```

The very first step: copy `tpcds_semantic_model.yaml` from the OSI repo's `examples/` directory into your `tests/fixtures/` directory, write this test, and make it pass.