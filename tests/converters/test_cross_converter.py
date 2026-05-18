from __future__ import annotations

import pytest

from osi_core.validator import validate_schema
from osi_core.converters.snowflake import SnowflakeConverter, SnowflakeImporter
from osi_core.converters.gooddata import GoodDataConverter, GoodDataImporter
from tests.helpers import load_yaml, load_json, FIXTURES_DIR


class TestSnowflakeToOsiToGoodData:
    """Snowflake → OSI → GoodData cross-converter integration."""

    @pytest.fixture
    def snowflake_dict(self) -> dict:
        return load_yaml(FIXTURES_DIR / "snowflake" / "tpcds.yaml")

    @pytest.fixture
    def intermediated_osi(self, snowflake_dict: dict) -> dict:
        return SnowflakeImporter().to_osi(snowflake_dict)

    def test_snowflake_to_osi_produces_valid_osi(self, intermediated_osi: dict):
        errors = validate_schema(intermediated_osi)
        assert errors == [], f"OSI validation errors: {errors}"

    def test_snowflake_to_osi_has_datasets(self, intermediated_osi: dict):
        for sm in intermediated_osi.get("semantic_model", []):
            assert sm.get("datasets"), "No datasets in OSI model"

    def test_snowflake_to_osi_to_gooddata_produces_dict(self, intermediated_osi: dict):
        gd = GoodDataConverter().from_osi(intermediated_osi)
        assert isinstance(gd, dict)
        assert "ldm" in gd


class TestGoodDataToOsiToSnowflake:
    """GoodData → OSI → Snowflake cross-converter integration.

    Note: GoodData uses different column naming and single-part table sources,
    so the intermediate OSI may not strictly validate (relationship refs use
    GoodData column IDs, sources may be unqualified). These tests verify the
    pipeline completes and produces reasonable output.
    """

    @pytest.fixture
    def gooddata_dict(self) -> dict:
        return load_json(FIXTURES_DIR / "gooddata_tpcds.json")

    def test_gooddata_to_osi_has_datasets(self, gooddata_dict: dict):
        osi_model = GoodDataImporter().to_osi(gooddata_dict)
        for sm in osi_model.get("semantic_model", []):
            assert sm.get("datasets"), "No datasets in OSI model"

    def test_gooddata_to_osi_completes_without_error(self, gooddata_dict: dict):
        """GoodData → OSI conversion completes (metrics are a known gap)."""
        osi_model = GoodDataImporter().to_osi(gooddata_dict)
        assert "semantic_model" in osi_model
        assert len(osi_model["semantic_model"]) > 0

    def test_gooddata_to_osi_to_snowflake_known_limitation(self, gooddata_dict: dict):
        """GoodData uses single-part table sources; Snowflake requires 3-part.

        This is a known format incompatibility — GoodData doesn't encode
        db.schema.table in its LDM, so the Snowflake exporter rejects it.
        """
        osi_model = GoodDataImporter().to_osi(gooddata_dict)
        from osi_core.converters.snowflake.exporter import OsiConversionError
        with pytest.raises(OsiConversionError, match="fully qualified"):
            SnowflakeConverter().from_osi(osi_model)
