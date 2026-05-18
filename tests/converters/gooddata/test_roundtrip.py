"""Round-trip conversion tests: GoodData → OSI → GoodData."""

from __future__ import annotations

from osi_core.converters.gooddata.importer import GoodDataImporter
from osi_core.converters.gooddata.exporter import GoodDataExporter


class TestRoundtrip:
    def test_roundtrip_preserves_datasets(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        exporter = GoodDataExporter()

        osi = importer.to_osi(gooddata_tpcds_dict, model_name="roundtrip_test")
        result = exporter.from_osi(osi)

        original_ds_ids = {ds["id"] for ds in gooddata_tpcds_dict["ldm"]["datasets"]}
        result_ds_ids = {ds["id"] for ds in result["ldm"]["datasets"]}

        assert original_ds_ids == result_ds_ids

    def test_roundtrip_preserves_date_instances(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        exporter = GoodDataExporter()

        osi = importer.to_osi(gooddata_tpcds_dict)
        result = exporter.from_osi(osi)

        assert len(result["ldm"]["dateInstances"]) == len(gooddata_tpcds_dict["ldm"]["dateInstances"])

        original_di = gooddata_tpcds_dict["ldm"]["dateInstances"][0]
        result_di = result["ldm"]["dateInstances"][0]
        assert result_di["id"] == original_di["id"]
        assert set(result_di["granularities"]) == set(original_di["granularities"])

    def test_roundtrip_preserves_references(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        exporter = GoodDataExporter()

        osi = importer.to_osi(gooddata_tpcds_dict)
        result = exporter.from_osi(osi)

        original_ss = next(ds for ds in gooddata_tpcds_dict["ldm"]["datasets"] if ds["id"] == "store_sales")
        result_ss = next(ds for ds in result["ldm"]["datasets"] if ds["id"] == "store_sales")

        original_targets = {ref["identifier"]["id"] for ref in original_ss["references"]}
        result_targets = {ref["identifier"]["id"] for ref in result_ss["references"]}
        assert original_targets == result_targets

    def test_roundtrip_preserves_attribute_count(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        exporter = GoodDataExporter()

        osi = importer.to_osi(gooddata_tpcds_dict)
        result = exporter.from_osi(osi)

        for orig_ds in gooddata_tpcds_dict["ldm"]["datasets"]:
            result_ds = next((ds for ds in result["ldm"]["datasets"] if ds["id"] == orig_ds["id"]), None)
            assert result_ds is not None
            assert len(result_ds["attributes"]) == len(orig_ds["attributes"])

    def test_roundtrip_preserves_fact_count(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        exporter = GoodDataExporter()

        osi = importer.to_osi(gooddata_tpcds_dict)
        result = exporter.from_osi(osi)

        for orig_ds in gooddata_tpcds_dict["ldm"]["datasets"]:
            result_ds = next((ds for ds in result["ldm"]["datasets"] if ds["id"] == orig_ds["id"]), None)
            assert result_ds is not None
            assert len(result_ds["facts"]) == len(orig_ds["facts"])
