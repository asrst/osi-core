"""Tests for GoodData declarative model serialization/deserialization."""

from __future__ import annotations

from osi_core.converters.gooddata.models import GdDeclarativeModel, gd_model_from_dict, gd_model_to_dict


def test_parse_gooddata_model(gooddata_tpcds_dict: dict, gooddata_tpcds_model: GdDeclarativeModel):
    """Verify parsing of the GoodData TPC-DS fixture."""
    ldm = gooddata_tpcds_model.ldm

    assert len(ldm.datasets) == 4
    assert len(ldm.date_instances) == 1

    store_sales = ldm.datasets[0]
    assert store_sales.id == "store_sales"
    assert len(store_sales.attributes) == 4
    assert len(store_sales.facts) == 4
    assert len(store_sales.grain) == 2
    assert len(store_sales.references) == 4

    assert store_sales.data_source_table_id is not None
    assert store_sales.data_source_table_id.data_source_id == "tpcds"
    assert store_sales.data_source_table_id.path == ["public", "store_sales"]

    customer = ldm.datasets[1]
    assert customer.id == "customer"
    assert len(customer.attributes[0].labels) == 2
    email_label = customer.attributes[0].labels[1]
    assert email_label.value_type == "HYPERLINK"

    date = ldm.date_instances[0]
    assert date.id == "date_dim"
    assert "DAY" in date.granularities


def test_roundtrip_serialization(gooddata_tpcds_dict: dict):
    """Verify that parsing and re-serializing produces equivalent output."""
    model = gd_model_from_dict(gooddata_tpcds_dict)
    result = gd_model_to_dict(model)

    assert len(result["ldm"]["datasets"]) == len(gooddata_tpcds_dict["ldm"]["datasets"])
    assert len(result["ldm"]["dateInstances"]) == len(gooddata_tpcds_dict["ldm"]["dateInstances"])

    ds = result["ldm"]["datasets"][0]
    assert ds["id"] == "store_sales"
    assert len(ds["attributes"]) == 4
    assert len(ds["facts"]) == 4
    assert len(ds["references"]) == 4

    di = result["ldm"]["dateInstances"][0]
    assert di["id"] == "date_dim"
    assert di["granularities"] == ["DAY", "WEEK", "MONTH", "QUARTER", "YEAR"]
