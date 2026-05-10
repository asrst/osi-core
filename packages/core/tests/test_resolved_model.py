import pytest
from osi_core.models import ResolvedModel, SemanticModel, Dataset, Field, Metric, Relationship
from osi_core.models.types import DialectExpr, DialectExpression, Dialect, Dimension


class TestResolvedModel:
    def test_default_spec_version(self):
        model = ResolvedModel(
            name="test",
            semantic_models=[],
        )
        assert model.osi_spec_version == "0.1.1"

    def test_custom_spec_version(self):
        model = ResolvedModel(
            osi_spec_version="0.2.0",
            name="test",
            semantic_models=[],
        )
        assert model.osi_spec_version == "0.2.0"

    def test_semantic_models_field(self):
        sm = SemanticModel(name="sales", datasets=[], metrics=[])
        model = ResolvedModel(
            name="test",
            semantic_models=[sm],
        )
        assert len(model.semantic_models) == 1
        assert model.semantic_models[0].name == "sales"

    def test_to_json(self):
        model = ResolvedModel(
            name="test",
            semantic_models=[],
        )
        json_str = model.to_json()
        assert "test" in json_str
        assert "0.1.1" in json_str

    def test_from_json(self):
        original = ResolvedModel(
            name="test",
            semantic_models=[],
        )
        json_str = original.to_json()
        restored = ResolvedModel.from_json(json_str)
        assert original == restored


class TestMetric:
    def test_metric_with_dialect_expression(self):
        expr = DialectExpression(dialects=[
            DialectExpr(dialect=Dialect.ANSI_SQL, expression="COUNT(*)"),
        ])
        metric = Metric(name="total", expression=expr)
        assert metric.name == "total"
        assert metric.expression.dialects[0].expression == "COUNT(*)"

    def test_metric_without_dialects(self):
        metric = Metric(name="total", expression=DialectExpression(dialects=[]))
        assert len(metric.expression.dialects) == 0


class TestDataset:
    def test_dataset_with_source(self):
        ds = Dataset(
            name="users",
            source="sales.public.users",
            primary_key=["id"],
            fields=[],
        )
        assert ds.name == "users"
        assert ds.source == "sales.public.users"
        assert ds.primary_key == ["id"]

    def test_dataset_with_composite_pk(self):
        ds = Dataset(
            name="order_lines",
            source="sales.public.order_lines",
            primary_key=["order_id", "line_number"],
            fields=[],
        )
        assert len(ds.primary_key) == 2

    def test_dataset_with_unique_keys(self):
        ds = Dataset(
            name="users",
            source="sales.public.users",
            unique_keys=[["email"], ["phone"]],
            fields=[],
        )
        assert len(ds.unique_keys) == 2


class TestField:
    def test_field_with_dialect_expression(self):
        expr = DialectExpression(dialects=[
            DialectExpr(dialect=Dialect.ANSI_SQL, expression="user_id"),
        ])
        field = Field(name="user_id", expression=expr)
        assert field.name == "user_id"
        assert field.expression.dialects[0].dialect == Dialect.ANSI_SQL

    def test_field_with_dimension(self):
        expr = DialectExpression(dialects=[
            DialectExpr(dialect=Dialect.ANSI_SQL, expression="order_date"),
        ])
        field = Field(
            name="order_date",
            expression=expr,
            dimension=Dimension(is_time=True),
        )
        assert field.dimension is not None
        assert field.dimension.is_time is True


class TestRelationship:
    def test_simple_relationship(self):
        rel = Relationship(
            name="orders_to_users",
            from_dataset="orders",
            to_dataset="users",
            from_columns=["user_id"],
            to_columns=["id"],
        )
        assert rel.from_dataset == "orders"
        assert len(rel.from_columns) == 1

    def test_composite_relationship(self):
        rel = Relationship(
            name="lines_to_products",
            from_dataset="order_lines",
            to_dataset="products",
            from_columns=["product_id", "variant_id"],
            to_columns=["id", "variant_id"],
        )
        assert len(rel.from_columns) == 2
        assert len(rel.to_columns) == 2


class TestSemanticModel:
    def test_semantic_model_with_all_components(self):
        ds = Dataset(name="orders", source="sales.public.orders", fields=[])
        expr = DialectExpression(dialects=[
            DialectExpr(dialect=Dialect.ANSI_SQL, expression="COUNT(*)"),
        ])
        metric = Metric(name="total_orders", expression=expr)
        rel = Relationship(
            name="orders_to_users",
            from_dataset="orders",
            to_dataset="users",
            from_columns=["user_id"],
            to_columns=["id"],
        )
        sm = SemanticModel(
            name="sales_model",
            datasets=[ds],
            relationships=[rel],
            metrics=[metric],
        )
        assert sm.name == "sales_model"
        assert len(sm.datasets) == 1
        assert len(sm.relationships) == 1
        assert len(sm.metrics) == 1