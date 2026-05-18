"""Tests for GoodData → OSI conversion (importer)."""

from __future__ import annotations

import json

from osi_core.converters.gooddata.importer import GoodDataImporter


class TestGoodDataImporter:
    def test_basic_conversion(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict, model_name="tpcds_test")

        assert result["version"] == "0.1.1"
        assert len(result["semantic_model"]) == 1

        sm = result["semantic_model"][0]
        assert sm["name"] == "tpcds_test"

    def test_datasets_converted(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict)
        sm = result["semantic_model"][0]

        assert len(sm["datasets"]) == 5

        names = {ds["name"] for ds in sm["datasets"]}
        assert "store_sales" in names
        assert "customer" in names
        assert "item" in names
        assert "store" in names
        assert "date_dim" in names

    def test_dataset_source(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict)
        sm = result["semantic_model"][0]

        store_sales = next(ds for ds in sm["datasets"] if ds["name"] == "store_sales")
        assert store_sales["source"] == "tpcds.public.store_sales"

    def test_primary_key_from_grain(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict)
        sm = result["semantic_model"][0]

        store_sales = next(ds for ds in sm["datasets"] if ds["name"] == "store_sales")
        assert set(store_sales["primary_key"]) == {"ss_item_sk", "ss_ticket_number"}

    def test_attributes_become_dimension_fields(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict)
        sm = result["semantic_model"][0]

        customer = next(ds for ds in sm["datasets"] if ds["name"] == "customer")
        fields = customer["fields"]

        assert len(fields) == 3

        for f in fields:
            assert "dimension" in f
            assert f["dimension"]["is_time"] is False

    def test_facts_become_plain_fields(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict)
        sm = result["semantic_model"][0]

        store_sales = next(ds for ds in sm["datasets"] if ds["name"] == "store_sales")
        fields = store_sales["fields"]

        assert len(fields) == 8

        fact_fields = [f for f in fields if "dimension" not in f]
        assert len(fact_fields) == 4

    def test_maql_expressions(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict)
        sm = result["semantic_model"][0]

        store_sales = next(ds for ds in sm["datasets"] if ds["name"] == "store_sales")
        quantity_field = next(f for f in store_sales["fields"] if f["name"] == "ss_quantity")
        dialects = quantity_field["expression"]["dialects"]
        assert len(dialects) == 2

        ansi = next(d for d in dialects if d["dialect"] == "ANSI_SQL")
        assert ansi["expression"] == "ss_quantity"

        maql = next(d for d in dialects if d["dialect"] == "MAQL")
        assert "store_sales.ss_quantity" in maql["expression"]

    def test_references_become_relationships(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict)
        sm = result["semantic_model"][0]

        rels = sm["relationships"]
        assert len(rels) == 4

        date_rel = next(r for r in rels if r["to"] == "date_dim")
        assert date_rel["from"] == "store_sales"
        assert date_rel["from_columns"] == ["ss_sold_date_sk"]

    def test_date_instance_converted(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict)
        sm = result["semantic_model"][0]

        date_ds = next(ds for ds in sm["datasets"] if ds["name"] == "date_dim")
        assert "custom_extensions" in date_ds

        ext = date_ds["custom_extensions"][0]
        assert ext["vendor_name"] == "GOODDATA"

        ext_data = json.loads(ext["data"])
        assert ext_data["date_dimension"] is True
        assert "DAY" in ext_data["granularities"]

    def test_labels_in_custom_extensions(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict)
        sm = result["semantic_model"][0]

        customer = next(ds for ds in sm["datasets"] if ds["name"] == "customer")
        sk_field = next(f for f in customer["fields"] if f["name"] == "c_customer_sk")

        assert "custom_extensions" in sk_field

        ext_data = json.loads(sk_field["custom_extensions"][0]["data"])
        assert ext_data["field_type"] == "attribute"
        assert len(ext_data["labels"]) == 2

        email_label = next(lb for lb in ext_data["labels"] if lb["id"] == "label.customer.c_email_address")
        assert email_label["value_type"] == "HYPERLINK"

    def test_data_source_id_extension(self, gooddata_tpcds_dict: dict):
        importer = GoodDataImporter()
        result = importer.to_osi(gooddata_tpcds_dict, data_source_id="my_pg")
        sm = result["semantic_model"][0]

        assert "custom_extensions" in sm

        ext_data = json.loads(sm["custom_extensions"][0]["data"])
        assert ext_data["data_source_id"] == "my_pg"
