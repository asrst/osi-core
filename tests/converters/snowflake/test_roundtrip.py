"""Round-trip conversion tests: OSI → Snowflake → OSI."""

import pytest
import yaml

from osi_core.converters.snowflake.exporter import SnowflakeExporter
from osi_core.converters.snowflake.importer import SnowflakeImporter
from osi_core.serializer import load_osi_yaml


@pytest.fixture
def exporter():
    return SnowflakeExporter()


@pytest.fixture
def importer():
    return SnowflakeImporter()


def _wrap_osi(model_dict):
    return {"version": "0.1.1", "semantic_model": [model_dict]}


class TestRoundtrip:
    def test_roundtrip_preserves_name(self, exporter, importer):
        osi = _wrap_osi({
            "name": "test_model",
            "datasets": [
                {
                    "name": "users",
                    "source": "db.schema.users",
                    "fields": [
                        {
                            "name": "id",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "id"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        }
                    ],
                }
            ],
            "metrics": [
                {
                    "name": "total",
                    "expression": {
                        "dialects": [
                            {"dialect": "ANSI_SQL", "expression": "COUNT(*)"}
                        ]
                    },
                }
            ],
        })
        sf = exporter.from_osi(osi)
        result = importer.to_osi(sf)
        assert result["semantic_model"][0]["name"] == "test_model"

    def test_roundtrip_preserves_table_count(self, exporter, importer):
        osi = _wrap_osi({
            "name": "m",
            "datasets": [
                {
                    "name": "t1",
                    "source": "db.s.t1",
                    "fields": [
                        {
                            "name": "id",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "id"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        }
                    ],
                },
                {
                    "name": "t2",
                    "source": "db.s.t2",
                    "fields": [
                        {
                            "name": "id",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "id"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        }
                    ],
                },
            ],
        })
        sf = exporter.from_osi(osi)
        result = importer.to_osi(sf)
        assert len(result["semantic_model"][0]["datasets"]) == 2

    def test_roundtrip_preserves_dimensions_and_facts(self, exporter, importer):
        osi = _wrap_osi({
            "name": "m",
            "datasets": [
                {
                    "name": "orders",
                    "source": "db.s.orders",
                    "fields": [
                        {
                            "name": "id",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "id"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        },
                        {
                            "name": "order_date",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL",
                                        "expression": "order_date"}
                                ]
                            },
                            "dimension": {"is_time": True},
                        },
                        {
                            "name": "amount",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL",
                                        "expression": "amount"}
                                ]
                            },
                        },
                    ],
                }
            ],
        })
        sf = exporter.from_osi(osi)
        result = importer.to_osi(sf)
        ds = result["semantic_model"][0]["datasets"][0]
        fields = ds["fields"]
        dims = [f for f in fields if f.get("dimension") and not f["dimension"]["is_time"]]
        time_dims = [f for f in fields if f.get("dimension") and f["dimension"]["is_time"]]
        facts = [f for f in fields if "dimension" not in f]
        assert len(dims) == 1
        assert len(time_dims) == 1
        assert len(facts) == 1

    def test_roundtrip_preserves_relationships(self, exporter, importer):
        osi = _wrap_osi({
            "name": "m",
            "datasets": [
                {
                    "name": "orders",
                    "source": "db.s.orders",
                    "fields": [
                        {
                            "name": "id",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "id"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        }
                    ],
                },
                {
                    "name": "users",
                    "source": "db.s.users",
                    "fields": [
                        {
                            "name": "id",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "id"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        }
                    ],
                },
            ],
            "relationships": [
                {
                    "name": "orders_users",
                    "from": "orders",
                    "to": "users",
                    "from_columns": ["user_id"],
                    "to_columns": ["id"],
                }
            ],
        })
        sf = exporter.from_osi(osi)
        result = importer.to_osi(sf)
        rels = result["semantic_model"][0]["relationships"]
        assert len(rels) == 1
        assert rels[0]["name"] == "orders_users"
        assert rels[0]["from_columns"] == ["user_id"]

    def test_roundtrip_preserves_metrics(self, exporter, importer):
        osi = _wrap_osi({
            "name": "m",
            "datasets": [
                {
                    "name": "t",
                    "source": "db.s.t",
                    "fields": [
                        {
                            "name": "id",
                            "expression": {
                                "dialects": [
                                    {"dialect": "ANSI_SQL", "expression": "id"}
                                ]
                            },
                            "dimension": {"is_time": False},
                        }
                    ],
                }
            ],
            "metrics": [
                {
                    "name": "total",
                    "expression": {
                        "dialects": [
                            {"dialect": "ANSI_SQL", "expression": "COUNT(*)"}
                        ]
                    },
                },
                {
                    "name": "sum_amount",
                    "expression": {
                        "dialects": [
                            {"dialect": "ANSI_SQL", "expression": "SUM(amount)"}
                        ]
                    },
                },
            ],
        })
        sf = exporter.from_osi(osi)
        result = importer.to_osi(sf)
        metrics = result["semantic_model"][0]["metrics"]
        assert len(metrics) == 2
        metric_names = {m["name"] for m in metrics}
        assert "total" in metric_names
        assert "sum_amount" in metric_names

    def test_roundtrip_tpcds(self, exporter, importer):
        """Full roundtrip using the TPC-DS reference model."""
        import yaml
        from pathlib import Path
        fixture = Path(__file__).parent.parent.parent / "fixtures" / "tpcds_semantic_model.yaml"
        osi_raw = load_osi_yaml(fixture)
        sf = exporter.from_osi(osi_raw)
        result = importer.to_osi(sf)
        sm = result["semantic_model"][0]
        assert sm["name"] == "tpcds_retail_model"
        assert len(sm["datasets"]) == 5
        assert len(sm["relationships"]) == 4
        assert len(sm["metrics"]) == 5
