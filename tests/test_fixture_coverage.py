from __future__ import annotations

from pathlib import Path

import pytest

from osi_core.serializer import load_osi_yaml
from osi_core.validator import validate_schema
from tests.helpers import list_fixtures, load_yaml


def _osi_fixtures() -> list[Path]:
    return list_fixtures("osi")


def _snowflake_fixtures() -> list[Path]:
    return list_fixtures("snowflake")


# Sidemantic's fixtures use a superset format (version "1.0", different
# relationship keys). Only our own fixtures strictly follow the OSI spec.
KNOWN_STRICT_OSI: set[str] = {"sample"}


class TestOsiFixtures:
    @pytest.mark.parametrize("path", _osi_fixtures(), ids=lambda p: p.stem)
    def test_parseable(self, path: Path):
        data = load_yaml(path)
        assert isinstance(data, dict), f"{path.name} is not a dict"

    @pytest.mark.parametrize("path", _osi_fixtures(), ids=lambda p: p.stem)
    def test_has_semantic_model(self, path: Path):
        data = load_yaml(path)
        has_sm = "semantic_model" in data
        has_datasets = any(
            isinstance(sm, dict) and "datasets" in sm
            for sm in data.get("semantic_model", [])
        )
        assert has_sm and has_datasets, f"{path.name}: no semantic_model with datasets"

    @pytest.mark.parametrize(
        "path",
        [p for p in _osi_fixtures() if p.stem in KNOWN_STRICT_OSI],
        ids=lambda p: p.stem,
    )
    def test_strict_validation(self, path: Path):
        data = load_osi_yaml(path)
        errors = validate_schema(data)
        assert errors == [], f"{path.name} validation errors: {errors}"


class TestSnowflakeFixturesImport:
    """Exercise SnowflakeImporter against every Snowflake fixture."""

    @pytest.mark.parametrize("path", _snowflake_fixtures(), ids=lambda p: p.stem)
    def test_import_to_osi(self, path: Path):
        from osi_core.converters.snowflake import SnowflakeImporter
        data = load_yaml(path)
        result = SnowflakeImporter().to_osi(data)
        assert isinstance(result, dict)
        assert "semantic_model" in result
        for sm in result["semantic_model"]:
            assert "datasets" in sm
            assert len(sm["datasets"]) > 0

    @pytest.mark.parametrize("path", _snowflake_fixtures(), ids=lambda p: p.stem)
    def test_imported_osi_validates(self, path: Path):
        from osi_core.converters.snowflake import SnowflakeImporter
        data = load_yaml(path)
        result = SnowflakeImporter().to_osi(data)
        errors = validate_schema(result)
        assert errors == [], f"{path.name} OSI validation errors: {errors}"


def test_tpcds_reference_validates():
    from tests.helpers import FIXTURES_DIR
    path = FIXTURES_DIR / "tpcds_semantic_model.yaml"
    data = load_osi_yaml(path)
    errors = validate_schema(data)
    assert errors == [], f"{path.name} validation errors: {errors}"


class TestSnowflakeFixtures:
    @pytest.mark.parametrize("path", _snowflake_fixtures(), ids=lambda p: p.stem)
    def test_parseable(self, path: Path):
        data = load_yaml(path)
        assert isinstance(data, dict), f"{path.name} is not a dict"

    @pytest.mark.parametrize("path", _snowflake_fixtures(), ids=lambda p: p.stem)
    def test_has_required_keys(self, path: Path):
        data = load_yaml(path)
        assert "name" in data, f"{path.name} missing 'name'"
        assert "tables" in data, f"{path.name} missing 'tables'"
        assert isinstance(data["tables"], list), f"{path.name} 'tables' must be a list"
