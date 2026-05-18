import pytest
from pathlib import Path
from osi_core.adapters import OsiAdapter
from osi_core.models import ResolvedModel
from osi_core.models.types import ParseResult, DialectExpr, DialectExpression, Dialect
from osi_core.resolver import resolve


class TestOsiAdapter:
    @pytest.fixture
    def sample_file(self):
        return Path(__file__).parent.parent / "fixtures" / "osi" / "sample.yaml"

    @pytest.fixture
    def adapter(self):
        return OsiAdapter()

    def test_format_name(self, adapter):
        assert adapter.format_name == "osi"

    def test_parse_yaml_file(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        assert isinstance(result, ParseResult)
        assert result.source_format == "osi"
        assert result.raw is not None

    def test_parse_detects_spec_version(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        assert result.osi_spec_version == "0.1.1"

    def test_parse_detects_legacy_version(self, adapter):
        legacy_yaml = """
name: legacy_model
datasets:
  - name: users
    fields:
      - name: id
        type: integer
metrics:
  - name: user_count
    expression: COUNT(*)
    type: additive
"""
        result = adapter.parse(legacy_yaml)
        assert result.source_version == "legacy"

    def test_parse_preserves_raw(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        assert "semantic_model" in result.raw
        assert "version" in result.raw

    def test_resolve_spec_format(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        assert isinstance(model, ResolvedModel)
        assert model.osi_spec_version == "0.1.1"
        assert len(model.semantic_models) == 1

        sm = model.semantic_models[0]
        assert sm.name == "ecommerce_analytics"
        assert len(sm.datasets) == 2
        assert len(sm.metrics) == 2

    def test_resolve_datasets(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        sm = model.semantic_models[0]

        users = next(ds for ds in sm.datasets if ds.name == "users")
        assert users.source == "sales.public.users"
        assert users.primary_key == ["id"]

        orders = next(ds for ds in sm.datasets if ds.name == "orders")
        assert len(orders.fields) == 3

    def test_resolve_fields(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        sm = model.semantic_models[0]

        orders = next(ds for ds in sm.datasets if ds.name == "orders")
        amount = next(f for f in orders.fields if f.name == "amount")
        assert amount.expression.dialects[0].dialect == Dialect.ANSI_SQL
        assert amount.expression.dialects[0].expression == "amount"

    def test_resolve_metrics(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        sm = model.semantic_models[0]

        user_count = next(m for m in sm.metrics if m.name == "user_count")
        assert user_count.expression.dialects[0].expression == "COUNT(DISTINCT users.id)"

    def test_resolve_relationships(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        sm = model.semantic_models[0]

        rel = next(r for r in sm.relationships if r.name == "orders_to_users")
        assert rel.from_dataset == "orders"
        assert rel.to_dataset == "users"
        assert rel.from_columns == ["user_id"]
        assert rel.to_columns == ["id"]

    def test_translate_spec_format(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        output = adapter.translate(model)

        assert "version:" in output
        assert "semantic_model:" in output
        assert "ecommerce_analytics" in output

    def test_translate_roundtrip(self, adapter, sample_file):
        result1 = adapter.parse(sample_file)
        model = resolve(result1)
        output = adapter.translate(model)

        result2 = adapter.parse(output)
        model2 = resolve(result2)

        assert model.name == model2.name
        assert len(model.semantic_models) == len(model2.semantic_models)
        sm1 = model.semantic_models[0]
        sm2 = model2.semantic_models[0]
        assert sm1.name == sm2.name
        assert len(sm1.datasets) == len(sm2.datasets)
        assert len(sm1.metrics) == len(sm2.metrics)

    def test_translate_preserves_expression(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        output = adapter.translate(model)

        result2 = adapter.parse(output)
        model2 = resolve(result2)
        sm1 = model.semantic_models[0]
        sm2 = model2.semantic_models[0]

        m1 = sm1.metrics[0]
        m2 = sm2.metrics[0]
        assert m1.expression.dialects[0].expression == m2.expression.dialects[0].expression