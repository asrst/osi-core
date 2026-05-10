# Migration Guide

This document covers spec migrations — converting metric definition files from one OSI spec version to another — and the migration tooling in semetric.

---

## When to Migrate

Migrate when:
- You have metric files written against an older OSI spec version
- You want to use new fields introduced in a newer spec version
- A tool or platform you're using requires a specific spec version

**Do not migrate blindly.** Migration changes the file format. Always review the diff before committing.

---

## The `migrate` Command

```bash
# Single file
semetric migrate input.yaml --from 0.1.1 --to 0.2.0 --output migrated.yaml

# In-place (modifies the file)
semetric migrate input.yaml --from 0.1.1 --to 0.2.0 --in-place

# Batch: migrate all YAML files in a directory
semetric migrate ./metrics/ --from 0.1.1 --to 0.2.0 --output ./migrated/

# Dry run: see what would change without modifying files
semetric migrate input.yaml --from 0.1.1 --to 0.2.0 --dry-run
```

### Flags

| Flag | Description |
|------|-------------|
| `--from` | Source OSI spec version (e.g., `0.1.1`) |
| `--to` | Target OSI spec version (e.g., `0.2.0`) |
| `--output` | Output file or directory (for batch) |
| `--in-place` | Overwrite the input file |
| `--dry-run` | Print the migrated output without writing |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Migration successful |
| 1 | Migration failed (error details in stderr) |
| 2 | Dry-run produced changes (informational; still exits 0) |

---

## How Migration Works

The migration command uses the same three-stage pipeline as translation:

```
OSI file (old version)
    │
    ▼
adapter.parse(source) → ParseResult (source_version tracked)
    │
    ▼
Resolver (handles spec version from file)
    │
    ▼
ResolvedModel (normalized to current spec, osi_spec_version tracked)
    │
    ▼
adapter.translate(model, target_version=target) → OSI file (new version)
```

The key is `target_version` in the adapter's `translate()` method. When specified, the adapter writes output in the requested spec version rather than the current one.

---

## Spec Version Transitions

### v0.1.1 → v0.2.0 (hypothetical example)

```yaml
# Before migration (v0.1.1)
semantic_model:
  - name: sales
    datasets:
      - name: orders
        source: sales.public.orders
        fields:
          - name: revenue
            type: decimal          # v0.1.1 uses flat field structure

# After migration (v0.2.0)
semantic_model:
  - name: sales
    datasets:
      - name: orders
        source: sales.public.orders
        fields:
          - name: revenue
            expression:           # v0.2.0 uses dialect expressions
              dialects:
                - dialect: ANSI_SQL
                  expression: revenue
            dimension:
              is_time: false
```

Changes introduced in the migration:
1. Flat `type` field → `expression.dialects[]` structure
2. `dimension.is_time` added (defaulted to `false`)
3. `ai_context` field added (populated if business context was available)

---

## Resolver Behavior During Migration

The shared resolver normalizes content to the **current** spec. It handles mapping old fields to new fields:

```python
def resolve_v011_to_current(parse_result: ParseResult) -> ResolvedModel:
    """
    - Maps flat type → DialectExpression with ANSI_SQL
    - Adds default dimension.is_time = False
    - Preserves custom_extensions
    - Tracks original osi_spec_version on the model
    """
```

When the resolver encounters a field it doesn't know (e.g., a v0.1.1 field that has no equivalent in v0.2.0), it:
1. Looks for a migration rule (e.g., `legacy_type_field → custom_extension`)
2. If no rule, preserves as `custom_extension` with `vendor_name: COMMON`

This means migration is **lossy for fields that don't map**. Always review custom_extensions in migrated output.

---

## Custom Extensions in Migration

Fields that don't exist in the target spec are preserved as `custom_extensions`:

```python
# Source file with a field not in OSI spec
custom_extensions:
  - vendor_name: COMMON
    data: '{"legacy_tag": "sales_v1"}'

# After migration to a newer spec, this extension persists on the model
# When written, it appears in the output YAML
```

To view what's in custom_extensions after migration:

```bash
semetric migrate input.yaml --from 0.1.1 --to 0.2.0 --dry-run | grep -A 5 custom_extensions
```

---

## Batch Migration

When migrating a directory, each file is processed independently:

```bash
semetric migrate ./metrics/ --from 0.1.1 --to 0.2.0 --output ./migrated/
```

- Input: `./metrics/a.yaml`, `./metrics/b.yaml`
- Output: `./migrated/a.yaml`, `./migrated/b.yaml`
- File names are preserved
- If `--output` is omitted, files are overwritten in place

---

## Limitations

1. **No automated refactoring**: Migration converts format, not semantics. A metric expression that needs manual editing still needs manual editing.
2. **Round-trip fidelity**: Files migrated forward then backward may not produce byte-identical output.
3. **custom_extensions accumulate**: Fields that never mapped to OSI will accumulate in `custom_extensions` across multiple migrations. Periodic cleanup may be needed.
4. **No partial migration**: All-or-nothing. Can't migrate selectively to a partial spec.

---

## Manual Migration

For complex migrations or when the automated tool isn't available:

```python
from osi_core import Translator

translator = Translator(adapters)

# Read with old adapter, resolve, write with new target version
model = translator.translate(
    source="metrics_v011.yaml",
    from_format="osi",
    to_format="osi",
    input_version="0.1.1",
    output_version="0.2.0",
)

print(model)  # Output YAML in v0.2.0 format
```

Or via the resolver directly:

```python
from semetric_osi_adapter import OsiAdapter
from osi_core.resolver import resolve

adapter = OsiAdapter()
parse_result = adapter.parse("metrics_v011.yaml", version="0.1.1")
model = resolve(parse_result)
output = adapter.translate(model, target_version="0.2.0")
print(output)
```

---

## Migration vs. Translation

| | Migration | Translation |
|-|-----------|-------------|
| Purpose | Convert file between OSI spec versions | Convert file between platform formats |
| Same format? | Yes (OSI → OSI) | No (OSI → Snowflake) |
| Target version? | Explicit (`--to`) | Optional (`--output-version`) |
| Resolver used? | Yes | Yes |
