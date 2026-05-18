# OSI Specification Alignment Notes

This document maps the OSI Core Metadata Specification v0.1.1 fields to the `ResolvedModel` canonical model, documents mapping rules for adapters, and tracks spec evolution decisions.

Reference: [OSI Core Spec](https://github.com/open-semantic-interchange/OSI/blob/main/core-spec/spec.md) · [OSI JSON Schema](https://github.com/open-semantic-interchange/OSI/blob/main/core-spec/osi-schema.json)

---

## Version Tracking

| OSI Spec Version | semetric Status | Notes |
|------------------|-----------------|-------|
| 0.1.1 | Supported | Initial release |

When the OSI spec is updated, update the table above and document the field-level changes below.

---

## Top-Level Fields

### Root

```yaml
version: "0.1.1"        # Required. OSI spec version. Stored as osi_spec_version.
dialects: [...]         # Declaration of supported dialects. Enumeration definition.
vendors: [...]          # Declaration of supported vendors. Enumeration definition.
semantic_model: [...]   # Array of one or more semantic models.
```

In `ResolvedModel`, `dialects` and `vendors` are treated as open enums rather than declared arrays. The spec version is the only required top-level field.

### Mapping: Root

| OSI Field | Canonical Model Field | Mapping Rule |
|-----------|---------------------|-------------|
| `version` | `osi_spec_version` | Direct. If absent, assume `0.1.1`. |
| `semantic_model[]` | `semantic_models: List[SemanticModel]` | Direct. Array maps to list. |
| `dialects[]` | `Dialect` enum | Checked at runtime. Unknown dialects log warning. |
| `vendors[]` | `Vendor` enum | Checked at runtime. Unknown vendors log warning. |

---

## SemanticModel

Container for datasets, relationships, and metrics.

```yaml
name: string            # Required. Unique identifier.
description: string     # Optional. Human-readable description.
ai_context: ...        # Optional. AI instructions and synonyms.
datasets: [...]         # Required. At least one dataset.
relationships: [...]    # Optional.
metrics: [...]          # Optional.
custom_extensions: ... # Optional. Vendor-specific metadata.
```

### Mapping: SemanticModel

| OSI Field | Canonical Model Field | Mapping Rule |
|-----------|----------------------|-------------|
| `name` | `SemanticModel.name` | Direct. |
| `description` | `SemanticModel.description` | Direct, optional. |
| `ai_context` | `SemanticModel.ai_context` | Maps to `AIContext` model. |
| `datasets[]` | `SemanticModel.datasets` | Direct list. |
| `relationships[]` | `SemanticModel.relationships` | Direct list. |
| `metrics[]` | `SemanticModel.metrics` | Direct list. |
| `custom_extensions[]` | `SemanticModel.custom_extensions` | Preserved as-is. |

---

## Dataset

Logical dataset (fact or dimension table). Contains fields and references a physical table.

```yaml
name: string            # Required. Unique identifier within the model.
source: string          # Required. Physical table reference (database.schema.table).
primary_key: [col]      # Optional. Single or composite primary key.
unique_keys: [[cols]]   # Optional. Array of unique key definitions.
description: string     # Optional.
ai_context: ...         # Optional.
fields: [...]            # Optional.
custom_extensions: ...  # Optional.
```

### Mapping: Dataset

| OSI Field | Canonical Model Field | Mapping Rule |
|-----------|----------------------|-------------|
| `name` | `Dataset.name` | Direct. |
| `source` | `Dataset.source` | Direct. Preserves full `database.schema.table` string. |
| `primary_key[]` | `Dataset.primary_key: List[str]` | Array to list. Single `[a]` and composite `[a, b]` both use same field. |
| `unique_keys[][]` | `Dataset.unique_keys: List[List[str]]` | Nested array to list of lists. |
| `description` | `Dataset.description` | Direct, optional. |
| `ai_context` | `Dataset.ai_context` | Maps to `AIContext`. |
| `fields[]` | `Dataset.fields: List[Field]` | Direct list. |
| `custom_extensions[]` | `Dataset.custom_extensions` | Preserved as-is. |

---

## Field

Row-level attribute for grouping, filtering, and metric expressions. Can be a column reference or computed expression.

```yaml
name: string            # Required. Unique within the dataset.
expression:             # Required. Expression with multi-dialect support.
  dialects:
    - dialect: ANSI_SQL
      expression: "customer_id"
dimension:              # Optional. Dimension metadata.
  is_time: boolean
label: string           # Optional. Display label.
description: string     # Optional.
ai_context: ...         # Optional.
custom_extensions: ... # Optional.
```

### Expression Object

Expressions support multiple SQL dialects:

```yaml
expression:
  dialects:
    - dialect: ANSI_SQL
      expression: LOWER(email)
    - dialect: SNOWFLAKE
      expression: LOWER(email)::VARCHAR
```

The adapter selects the best dialect for the target platform. If the target dialect isn't available, fall back to `ANSI_SQL`. If that's not available either, use the first available dialect and log a warning.

### Mapping: Field

| OSI Field | Canonical Model Field | Mapping Rule |
|-----------|----------------------|-------------|
| `name` | `Field.name` | Direct. |
| `expression` | `Field.expression: DialectExpression` | Required. Wrap single-string expressions in `ANSI_SQL` dialect. |
| `dimension.is_time` | `Field.dimension.is_time` | Optional. Default `False` if `dimension` absent. |
| `label` | `Field.label` | Direct, optional. |
| `description` | `Field.description` | Direct, optional. |
| `ai_context` | `Field.ai_context` | Maps to `AIContext`. |
| `custom_extensions[]` | `Field.custom_extensions` | Preserved as-is. |

### Legacy Field Mapping (v0.1.x → current)

OSI v0.1.1 uses flat field definitions without `expression.dialects`:

```yaml
# Legacy (pre-expression-object)
fields:
  - name: revenue
    type: decimal
```

**Migration rule**: Map `type` (e.g., `decimal`) to:
```yaml
expression:
  dialects:
    - dialect: ANSI_SQL
      expression: revenue  # column reference
dimension:
  is_time: false
```

---

## Relationship

Foreign key connection between datasets. Supports simple and composite keys.

```yaml
name: string       # Required. Unique identifier.
from: string       # Required. Dataset on the many side.
to: string         # Required. Dataset on the one side.
from_columns: [col] # Required. Foreign key columns.
to_columns: [col]  # Required. Primary/unique key columns.
ai_context: ...    # Optional.
custom_extensions: ... # Optional.
```

### Composite Keys

Both `from_columns` and `to_columns` must have the same number of elements. The order is positional:

```yaml
from_columns: [product_id, variant_id]
to_columns: [id, variant_id]
# Means: from.product_id = to.id AND from.variant_id = to.variant_id
```

### Mapping: Relationship

| OSI Field | Canonical Model Field | Mapping Rule |
|-----------|----------------------|-------------|
| `name` | `Relationship.name` | Direct. |
| `from` | `Relationship.from_dataset` | Direct. Stores the dataset name (not index). |
| `to` | `Relationship.to_dataset` | Direct. |
| `from_columns[]` | `Relationship.from_columns: List[str]` | Direct array. |
| `to_columns[]` | `Relationship.to_columns: List[str]` | Direct array. Must match `from_columns` length. |
| `ai_context` | `Relationship.ai_context` | Maps to `AIContext`. |
| `custom_extensions[]` | `Relationship.custom_extensions` | Preserved as-is. |

---

## Metric

Quantitative measure defined at the semantic model level. Can span multiple datasets.

```yaml
name: string        # Required. Unique identifier.
expression:        # Required. Multi-dialect aggregate expression.
  dialects:
    - dialect: ANSI_SQL
      expression: SUM(orders.amount)
description: string # Optional.
ai_context: ...     # Optional.
custom_extensions: ... # Optional.
```

### Cross-Dataset Metrics

Metrics can reference fields from multiple datasets:

```yaml
- name: avg_order_value
  expression:
    dialects:
      - dialect: ANSI_SQL
        expression: SUM(orders.amount) / COUNT(DISTINCT customers.id)
```

The resolver validates that all referenced datasets exist in the model.

### Mapping: Metric

| OSI Field | Canonical Model Field | Mapping Rule |
|-----------|----------------------|-------------|
| `name` | `Metric.name` | Direct. |
| `expression` | `Metric.expression: DialectExpression` | Required. Multi-dialect. |
| `description` | `Metric.description` | Direct, optional. |
| `ai_context` | `Metric.ai_context` | Maps to `AIContext`. |
| `custom_extensions[]` | `Metric.custom_extensions` | Preserved as-is. |

---

## AIContext

Additional context for AI tools. Can be a simple string or a structured object.

```yaml
# Simple string
ai_context: "orders, purchases, sales"

# Structured object
ai_context:
  instructions: "Use this for sales analysis"
  synonyms:
    - "orders"
    - "purchases"
  examples:
    - "Show total sales last month"
```

### Mapping: AIContext

| OSI Field | Canonical Model Field | Mapping Rule |
|-----------|----------------------|-------------|
| `ai_context: string` | `AIContext(instructions=string)` | Wrapped. |
| `ai_context: object` | `AIContext` | Direct mapping. Unknown fields preserved in `ai_context.custom_data`. |

### AIContext Model

```python
class AIContext(BaseModel):
    instructions: Optional[str] = None
    synonyms: List[str] = []
    examples: List[str] = []
```

If a platform provides AI context through a different mechanism (e.g., descriptions, column comments), extract it and map to `AIContext` during resolution.

---

## Custom Extensions

Vendor-specific metadata that doesn't have an OSI equivalent. Preserved on read and applied on write.

```yaml
custom_extensions:
  - vendor_name: SNOWFLAKE
    data: '{"warehouse": "ANALYTICS_WH", "database": "PROD"}'
  - vendor_name: DBT
    data: '{"materialized": "table", "tags": ["daily"]}'
```

### Mapping: CustomExtensions

| OSI Field | Canonical Model Field | Mapping Rule |
|-----------|----------------------|-------------|
| `custom_extensions[]` | Each level has `custom_extensions: List[CustomExtension]` | Preserved at dataset, field, relationship, metric, and semantic model level. |

### Extension Application (Write)

On write, apply extensions matching the target platform:

```python
def apply_extensions(data: Dict, model: ResolvedModel, vendor: Vendor) -> Dict:
    for ext in model.custom_extensions:
        if ext.vendor_name == vendor:
            config = json.loads(ext.data)
            # Apply config to output data structure
            ...
    return data
```

Extensions with non-matching `vendor_name` are preserved for round-tripping but not applied.

---

## Known Gaps

These fields exist in the OSI spec but are not yet fully supported in `ResolvedModel`:

| Field | Location | Status |
|-------|-----------|--------|
| `unique_keys` | Dataset | Defined but not yet in canonical model |
| `label` | Field | Defined in canonical model |
| `ai_context` at all levels | Multiple | Defined but integration testing needed |

---

## Enums

### Dialects

```python
class Dialect(Enum):
    ANSI_SQL = "ANSI_SQL"
    SNOWFLAKE = "SNOWFLAKE"
    MDX = "MDX"
    TABLEAU = "TABLEAU"
    DATABRICKS = "DATABRICKS"
    MAQL = "MAQL"
```

### Vendors

```python
class Vendor(Enum):
    COMMON = "COMMON"
    SNOWFLAKE = "SNOWFLAKE"
    SALESFORCE = "SALESFORCE"
    DBT = "DBT"
    DATABRICKS = "DATABRICKS"
    GOODDATA = "GOODDATA"
```
