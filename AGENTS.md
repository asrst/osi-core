# Development

- **Package manager**: `uv` (not pip). Use `uv sync` to install, `uv run pytest` to test.
- **Python**: 3.12 (`.python-version`)
- **No lint/typecheck config** (ruff.toml, pyrightconfig.json) — tools are in dev dependencies but not configured yet.

# Structure

- `src/osi_core/` — main implementation package
- `src/osi/` — optional CLI wrapper (can be removed once entry point is updated)
- Dev deps live in root `pyproject.toml`

# Commands

```bash
uv sync                    # install all deps
uv run pytest              # run all tests
uv run pytest packages/core/tests/test_readers/test_osi.py  # single test file
```

CLI (via `osi-core` entry point):
```bash
osi-core validate metrics.yaml --format osi
osi-core translate metrics.yaml --from osi --to osi
osi-core diff old.yaml new.yaml
```

# Testing

Fixtures live in `tests/fixtures/`. Snapshot tests use `syrupy` — run `pytest --snapshot-update` to update snapshots.