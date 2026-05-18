"""Tests for OSI → GoodData conversion (exporter)."""

from __future__ import annotations

from osi_core.converters.gooddata.exporter import GoodDataExporter
from osi_core.converters.gooddata.models import gd_model_from_dict


def test_basic_conversion(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict, data_source_id="tpcds")
    model = gd_model_from_dict(result)

    assert len(model.ldm.datasets) == 4
    assert len(model.ldm.date_instances) == 1


def test_dataset_ids(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict)
    model = gd_model_from_dict(result)

    ids = {ds.id for ds in model.ldm.datasets}
    assert "store_sales" in ids
    assert "customer" in ids
    assert "item" in ids
    assert "store" in ids


def test_date_dimension_detected(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict)
    model = gd_model_from_dict(result)

    assert len(model.ldm.date_instances) == 1
    di = model.ldm.date_instances[0]
    assert di.id == "date_dim"
    assert "DAY" in di.granularities
    assert "YEAR" in di.granularities


def test_dimension_fields_become_attributes(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict)
    model = gd_model_from_dict(result)

    customer = next(ds for ds in model.ldm.datasets if ds.id == "customer")
    assert len(customer.attributes) == 3
    assert len(customer.facts) == 0


def test_non_dimension_fields_become_facts(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict)
    model = gd_model_from_dict(result)

    store_sales = next(ds for ds in model.ldm.datasets if ds.id == "store_sales")
    assert len(store_sales.attributes) == 4
    assert len(store_sales.facts) == 4


def test_maql_expression_detection(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict)
    model = gd_model_from_dict(result)

    store_sales = next(ds for ds in model.ldm.datasets if ds.id == "store_sales")
    fact_ids = {f.id for f in store_sales.facts}
    assert any("ss_quantity" in fid for fid in fact_ids)
    assert any("ss_net_profit" in fid for fid in fact_ids)


def test_grain_from_primary_key(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict)
    model = gd_model_from_dict(result)

    store_sales = next(ds for ds in model.ldm.datasets if ds.id == "store_sales")
    grain_ids = {g.id for g in store_sales.grain}
    assert len(grain_ids) == 2


def test_relationships_become_references(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict)
    model = gd_model_from_dict(result)

    store_sales = next(ds for ds in model.ldm.datasets if ds.id == "store_sales")
    assert len(store_sales.references) == 4

    ref_targets = {ref.identifier.id for ref in store_sales.references}
    assert "date_dim" in ref_targets
    assert "customer" in ref_targets
    assert "item" in ref_targets
    assert "store" in ref_targets


def test_source_column_from_ansi_sql(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict)
    model = gd_model_from_dict(result)

    customer = next(ds for ds in model.ldm.datasets if ds.id == "customer")
    source_cols = {a.source_column for a in customer.attributes}
    assert "c_customer_sk" in source_cols
    assert "c_first_name" in source_cols


def test_data_source_table_id(osi_tpcds_dict: dict):
    exporter = GoodDataExporter()
    result = exporter.from_osi(osi_tpcds_dict, data_source_id="tpcds")
    model = gd_model_from_dict(result)

    store_sales = next(ds for ds in model.ldm.datasets if ds.id == "store_sales")
    assert store_sales.data_source_table_id is not None
    assert store_sales.data_source_table_id.data_source_id == "tpcds"
    assert "store_sales" in store_sales.data_source_table_id.path
