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
- (removed `src/osi/` wrapper — entry point now uses `osi` directly)
- `tests/fixtures/` — per-vendor fixture subdirs (`osi/`, `snowflake/`, plus root-level canonical fixtures)
- Dev deps live in root `pyproject.toml`

# Commands

```bash
uv sync                    # install all deps
uv run pytest              # run all 224+ tests
uv run pytest -k snowflake # run only Snowflake-related tests
uv run pytest -k gooddata  # run only GoodData-related tests
```

CLI (via `osi` entry point):
```bash
osi validate metrics.yaml
osi convert -i metrics.yaml --to snowflake -o output.yaml            # OSI → Snowflake
osi convert -i model.yaml --from snowflake -o osi_output.yaml        # Snowflake → OSI
osi convert -i osi_model.yaml --to gooddata -o gooddata_output.json  # OSI → GoodData
osi diff old.yaml new.yaml
osi list-converters
```

# Testing

- Fixtures live in `tests/fixtures/` — per-vendor subdirs for sidemantic fixtures, root level for canonical (TPC-DS) fixtures
- No snapshot tests currently active; `syrupy` is a dev dep but not used
- `tests/test_fixture_coverage.py` verifies every fixture parses and converts correctly
- `tests/test_base.py` verifies every converter implements the `BaseConverter` contract
- GoodData tests match the official OSI repo test suite (test_gooddata_to_osi.py etc.)
