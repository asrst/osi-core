# Development

- **Package manager**: `uv` (not pip). Use `uv sync` to install, `uv run pytest` to test.
- **Python**: 3.12 (`.python-version`)
- **No lint/typecheck config** (ruff.toml, pyrightconfig.json) — tools are in dev dependencies but not configured yet.

# Structure

- `src/osi_core/` — main implementation package
  - `converters/snowflake/` — Snowflake bidirectional converter
  - `converters/gooddata/` — GoodData bidirectional converter (ported from official OSI repo)
  - `dialects.py` — OSI→sqlglot dialect mapping
  - `normalizer.py` — shared identifier normalization & source parsing
- `src/osi/` — optional CLI wrapper (can be removed once entry point is updated)
- `tests/fixtures/` — per-vendor fixture subdirs (`osi/`, `snowflake/`, plus root-level canonical fixtures)
- Dev deps live in root `pyproject.toml`

# Commands

```bash
uv sync                    # install all deps
uv run pytest              # run all 224+ tests
uv run pytest -k snowflake # run only Snowflake-related tests
uv run pytest -k gooddata  # run only GoodData-related tests
```

CLI (via `osi-core` entry point):
```bash
osi-core validate metrics.yaml --format osi
osi-core convert snowflake export metrics.yaml -o output.yaml
osi-core convert snowflake import snowflake_model.yaml -o osi_output.yaml
osi-core convert gooddata export osi_model.yaml -o gooddata_output.json
osi-core diff old.yaml new.yaml
osi-core list-converters
```

# Testing

- Fixtures live in `tests/fixtures/` — per-vendor subdirs for sidemantic fixtures, root level for canonical (TPC-DS) fixtures
- No snapshot tests currently active; `syrupy` is a dev dep but not used
- `tests/test_fixture_coverage.py` verifies every fixture parses and converts correctly
- `tests/test_base.py` verifies every converter implements the `BaseConverter` contract
- GoodData tests match the official OSI repo test suite (test_gooddata_to_osi.py etc.)
