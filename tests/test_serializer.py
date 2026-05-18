from pathlib import Path

import pytest

from osi_core.serializer import (
    dump_osi_model,
    dump_osi_yaml,
    load_osi_model,
    load_osi_yaml,
)
from osi_core.models import ResolvedModel, SemanticModel, Dataset, Field, Metric
from osi_core.models.types import DialectExpr, DialectExpression, Dialect, Dimension


FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# load_osi_yaml / dump_osi_yaml roundtrip
# ---------------------------------------------------------------------------


def test_load_and_dump_roundtrip():
    fixture = FIXTURES / "tpcds_semantic_model.yaml"
    data = load_osi_yaml(fixture)
    output = dump_osi_yaml(data)
    round_trip = load_osi_yaml(output)

    assert round_trip["version"] == data["version"]
    assert round_trip["semantic_model"][0]["name"] == data["semantic_model"][0]["name"]
    assert isinstance(round_trip, dict)


def test_load_json_string():
    json_input = '{"version": "0.1.1", "semantic_model": []}'
    from osi_core.serializer import load_osi_json

    data = load_osi_json(json_input)
    assert data["version"] == "0.1.1"
    assert data["semantic_model"] == []


# ---------------------------------------------------------------------------
# load_osi_model / dump_osi_model (resolve + serialize)
# ---------------------------------------------------------------------------


def test_load_osi_model_from_yaml():
    fixture = FIXTURES / "osi" / "sample.yaml"
    model = load_osi_model(fixture)
    assert isinstance(model, ResolvedModel)
    assert model.osi_spec_version == "0.1.1"
    assert len(model.semantic_models) == 1
    sm = model.semantic_models[0]
    assert sm.name == "ecommerce_analytics"
    assert len(sm.datasets) == 2
    assert len(sm.metrics) == 2


def test_dump_osi_model_roundtrip():
    fixture = FIXTURES / "osi" / "sample.yaml"
    model1 = load_osi_model(fixture)
    output = dump_osi_model(model1)
    model2 = load_osi_model(output)

    assert model1.name == model2.name
    assert len(model1.semantic_models) == len(model2.semantic_models)
    sm1 = model1.semantic_models[0]
    sm2 = model2.semantic_models[0]
    assert sm1.name == sm2.name
    assert len(sm1.datasets) == len(sm2.datasets)
    assert len(sm1.metrics) == len(sm2.metrics)


def test_dump_osi_model_preserves_expression():
    fixture = FIXTURES / "osi" / "sample.yaml"
    model1 = load_osi_model(fixture)
    output = dump_osi_model(model1)
    model2 = load_osi_model(output)
    sm1 = model1.semantic_models[0]
    sm2 = model2.semantic_models[0]
    m1 = sm1.metrics[0]
    m2 = sm2.metrics[0]
    assert m1.expression.dialects[0].expression == m2.expression.dialects[0].expression


# ---------------------------------------------------------------------------
# Resolve tests (was test_resolver.py)
# ---------------------------------------------------------------------------


def test_resolve_spec_format_with_semantic_model_array():
    raw_str = """
version: "0.1.1"
semantic_model:
  - name: test_model
    datasets:
      - name: users
        source: sales.public.users
        fields:
          - name: id
            expression:
              dialects:
                - dialect: ANSI_SQL
                  expression: id
    metrics:
      - name: total_users
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: COUNT(*)
    relationships: []
"""
    model = load_osi_model(raw_str)
    assert model.osi_spec_version == "0.1.1"
    assert len(model.semantic_models) == 1
    sm = model.semantic_models[0]
    assert sm.name == "test_model"
    assert len(sm.datasets) == 1
    assert sm.datasets[0].name == "users"
    assert sm.datasets[0].source == "sales.public.users"
    assert len(sm.metrics) == 1
    assert sm.metrics[0].name == "total_users"
    assert sm.metrics[0].expression.dialects[0].dialect == Dialect.ANSI_SQL


def test_resolve_flat_format():
    raw_str = """
name: flat_model
datasets:
  - name: users
    source: sales.public.users
    fields:
      - name: id
        type: integer
metrics:
  - name: user_count
    expression: COUNT(*)
"""
    model = load_osi_model(raw_str)
    assert len(model.semantic_models) == 1
    sm = model.semantic_models[0]
    assert sm.name == "flat_model"
    assert len(sm.datasets) == 1
    ds = sm.datasets[0]
    assert ds.name == "users"
    assert ds.source == "sales.public.users"
    assert len(ds.fields) == 1
    f = ds.fields[0]
    assert f.name == "id"
    assert f.expression.dialects[0].dialect == Dialect.ANSI_SQL


def test_resolve_preserves_custom_extensions():
    raw_str = """
version: "0.1.1"
custom_extensions:
  - vendor_name: SNOWFLAKE
    data: '{"warehouse": "ANALYTICS_WH"}'
semantic_model:
  - name: test
    datasets: []
    metrics: []
    relationships: []
"""
    model = load_osi_model(raw_str)
    assert len(model.custom_extensions) == 1
    assert model.custom_extensions[0].vendor_name.value == "SNOWFLAKE"


def test_resolve_multiple_dialects():
    raw_str = """
version: "0.1.1"
semantic_model:
  - name: test
    datasets:
      - name: users
        source: sales.public.users
        fields:
          - name: email
            expression:
              dialects:
                - dialect: ANSI_SQL
                  expression: LOWER(email)
                - dialect: SNOWFLAKE
                  expression: LOWER(email)::VARCHAR
    metrics: []
    relationships: []
"""
    model = load_osi_model(raw_str)
    sm = model.semantic_models[0]
    email = sm.datasets[0].fields[0]
    assert len(email.expression.dialects) == 2
    assert email.expression.dialects[0].dialect == Dialect.ANSI_SQL
    assert email.expression.dialects[1].dialect == Dialect.SNOWFLAKE


def test_resolve_relationship_from_to_columns():
    raw_str = """
version: "0.1.1"
semantic_model:
  - name: test
    datasets:
      - name: orders
        source: sales.public.orders
        fields: []
      - name: users
        source: sales.public.users
        fields: []
    relationships:
      - name: orders_users
        from: orders
        to: users
        from_columns: [user_id]
        to_columns: [id]
    metrics: []
"""
    model = load_osi_model(raw_str)
    sm = model.semantic_models[0]
    rel = sm.relationships[0]
    assert rel.from_dataset == "orders"
    assert rel.to_dataset == "users"
    assert rel.from_columns == ["user_id"]
    assert rel.to_columns == ["id"]


def test_resolve_dimension_is_time():
    raw_str = """
version: "0.1.1"
semantic_model:
  - name: test
    datasets:
      - name: orders
        source: sales.public.orders
        fields:
          - name: order_date
            expression:
              dialects:
                - dialect: ANSI_SQL
                  expression: order_date
            dimension:
              is_time: true
    metrics: []
    relationships: []
"""
    model = load_osi_model(raw_str)
    sm = model.semantic_models[0]
    f = sm.datasets[0].fields[0]
    assert f.dimension is not None
    assert f.dimension.is_time is True
