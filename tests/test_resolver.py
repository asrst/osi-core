import pytest
from osi_core.models import ResolvedModel, SemanticModel, Dataset, Field, Metric
from osi_core.models.types import DialectExpr, DialectExpression, Dialect
from osi_core.resolver import resolve
from osi_core.models.types import ParseResult


class TestResolve:
    def test_resolve_spec_format_with_semantic_model_array(self):
        raw = {
            "version": "0.1.1",
            "semantic_model": [
                {
                    "name": "test_model",
                    "datasets": [
                        {
                            "name": "users",
                            "source": "sales.public.users",
                            "fields": [
                                {
                                    "name": "id",
                                    "expression": {
                                        "dialects": [
                                            {"dialect": "ANSI_SQL", "expression": "id"}
                                        ]
                                    }
                                }
                            ]
                        }
                    ],
                    "metrics": [
                        {
                            "name": "total_users",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "COUNT(*)"}
                                ]
                            }
                        }
                    ],
                    "relationships": []
                }
            ]
        }
        parse_result = ParseResult(raw=raw, source_format="osi", source_version="0.1.1")
        model = resolve(parse_result)

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

    def test_resolve_flat_format(self):
        raw = {
            "name": "flat_model",
            "datasets": [
                {
                    "name": "users",
                    "source": "sales.public.users",
                    "fields": [
                        {"name": "id", "type": "integer"}
                    ]
                }
            ],
            "metrics": [
                {"name": "user_count", "expression": "COUNT(*)"}
            ]
        }
        parse_result = ParseResult(raw=raw, source_format="osi", source_version="legacy")
        model = resolve(parse_result)

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

    def test_resolve_preserves_custom_extensions(self):
        raw = {
            "version": "0.1.1",
            "custom_extensions": [
                {"vendor_name": "SNOWFLAKE", "data": '{"warehouse": "ANALYTICS_WH"}'}
            ],
            "semantic_model": [
                {
                    "name": "test",
                    "datasets": [],
                    "metrics": [],
                    "relationships": []
                }
            ]
        }
        parse_result = ParseResult(raw=raw, source_format="osi", source_version="0.1.1")
        model = resolve(parse_result)
        assert len(model.custom_extensions) == 1
        assert model.custom_extensions[0].vendor_name.value == "SNOWFLAKE"

    def test_resolve_multiple_dialects(self):
        raw = {
            "version": "0.1.1",
            "semantic_model": [
                {
                    "name": "test",
                    "datasets": [
                        {
                            "name": "users",
                            "source": "sales.public.users",
                            "fields": [
                                {
                                    "name": "email",
                                    "expression": {
                                        "dialects": [
                                            {"dialect": "ANSI_SQL", "expression": "LOWER(email)"},
                                            {"dialect": "SNOWFLAKE", "expression": "LOWER(email)::VARCHAR"}
                                        ]
                                    }
                                }
                            ]
                        }
                    ],
                    "metrics": [],
                    "relationships": []
                }
            ]
        }
        parse_result = ParseResult(raw=raw, source_format="osi", source_version="0.1.1")
        model = resolve(parse_result)
        sm = model.semantic_models[0]
        email = sm.datasets[0].fields[0]
        assert len(email.expression.dialects) == 2
        assert email.expression.dialects[0].dialect == Dialect.ANSI_SQL
        assert email.expression.dialects[1].dialect == Dialect.SNOWFLAKE

    def test_resolve_relationship_from_to_columns(self):
        raw = {
            "version": "0.1.1",
            "semantic_model": [
                {
                    "name": "test",
                    "datasets": [
                        {"name": "orders", "source": "sales.public.orders", "fields": []},
                        {"name": "users", "source": "sales.public.users", "fields": []},
                    ],
                    "relationships": [
                        {
                            "name": "orders_users",
                            "from": "orders",
                            "to": "users",
                            "from_columns": ["user_id"],
                            "to_columns": ["id"]
                        }
                    ],
                    "metrics": []
                }
            ]
        }
        parse_result = ParseResult(raw=raw, source_format="osi", source_version="0.1.1")
        model = resolve(parse_result)
        sm = model.semantic_models[0]
        rel = sm.relationships[0]
        assert rel.from_dataset == "orders"
        assert rel.to_dataset == "users"
        assert rel.from_columns == ["user_id"]
        assert rel.to_columns == ["id"]

    def test_resolve_dimension_is_time(self):
        raw = {
            "version": "0.1.1",
            "semantic_model": [
                {
                    "name": "test",
                    "datasets": [
                        {
                            "name": "orders",
                            "source": "sales.public.orders",
                            "fields": [
                                {
                                    "name": "order_date",
                                    "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "order_date"}]},
                                    "dimension": {"is_time": True}
                                }
                            ]
                        }
                    ],
                    "metrics": [],
                    "relationships": []
                }
            ]
        }
        parse_result = ParseResult(raw=raw, source_format="osi", source_version="0.1.1")
        model = resolve(parse_result)
        sm = model.semantic_models[0]
        f = sm.datasets[0].fields[0]
        assert f.dimension is not None
        assert f.dimension.is_time is True