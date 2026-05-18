# osi-core

An OSI Native Metric Compiler/Converter — hub-and-spoke translation for metric definitions.

## What is OSI?

OSI (Open Semantic Interchange) is an open specification for defining and exchanging metric
definitions across tools and platforms. See the [OSI core spec](https://github.com/open-semantic-interchange/OSI/tree/main/core-spec)
and the [OSI converters](https://github.com/open-semantic-interchange/OSI/blob/main/converters/).

## Converters

| Direction | Vendor | Status |
|-----------|--------|--------|
| OSI ↔ Snowflake | [Snowflake Cortex Analyst](https://docs.snowflake.com/en/user-guide/semantic-model) | ✅ Both directions |
| OSI ↔ GoodData | [GoodData declarative LDM](https://www.gooddata.com/docs/cloud/api-and-sdk/api/declarative-ldm/) | ✅ Both directions |

Each converter follows the [OSI hub-and-spoke architecture](https://github.com/open-semantic-interchange/OSI/blob/main/converters/index.md).
Converters import vendor models into OSI and export OSI models into vendor formats.

## Quick Start

```bash
uv sync
```

```bash
# Validate an OSI YAML file
osi validate metrics.yaml

# Convert OSI → Snowflake
osi convert -i metrics.yaml --to snowflake -o snowflake_output.yaml

# Convert Snowflake → OSI
osi convert -i snowflake_model.yaml --from snowflake -o osi_output.yaml

# Convert OSI → GoodData
osi convert -i osi_model.yaml --to gooddata -o gooddata_output.json

# Diff two model files
osi diff old.yaml new.yaml

# List available converters
osi list-converters
```

## Development

```bash
uv sync                    # install all deps
uv run pytest              # run all tests
uv run pytest -k snowflake # run Snowflake-specific tests
uv run pytest -k gooddata  # run GoodData-specific tests
```

See [`docs/DEVELOPER.md`](docs/DEVELOPER.md) for more details.

## Project Structure

```
src/osi_core/
├── __init__.py             # Package exports (DIALECT_MAP, select_dialect, converter discovery)
├── cli.py                  # CLI entry point
├── dialects.py             # OSI→sqlglot dialect mapping
├── normalizer.py           # Shared identifier normalization and source parsing
├── serializer.py           # YAML/JSON serialization helpers
├── validator.py            # OSI schema validation
├── converters/
│   ├── base.py             # BaseConverter ABC
│   ├── snowflake/          # Snowflake importer + exporter + composite converter
│   └── gooddata/           # GoodData importer + exporter + composite converter

tests/
├── fixtures/
│   ├── osi/                # OSI YAML fixtures (sidemantic + canonical)
│   ├── snowflake/          # Snowflake YAML fixtures (sidemantic + canonical)
│   ├── gooddata_tpcds.json # Canonical GoodData TPC-DS fixture
│   ├── osi_tpcds.yaml      # Canonical OSI TPC-DS fixture
│   └── tpcds_semantic_model.yaml  # Reference OSI TPC-DS model
├── helpers.py              # Shared test utilities
├── test_fixture_coverage.py  # Verifies every fixture parses and converts
├── test_normalizer.py      # Tests for normalizer utilities
├── test_base.py            # Contract tests for BaseConverter subclasses
├── converters/
│   ├── test_cross_converter.py  # Snowflake↔OSI↔GoodData integration
│   ├── snowflake/          # Snowflake importer, exporter, roundtrip tests
│   └── gooddata/           # GoodData importer, exporter, roundtrip tests
```
