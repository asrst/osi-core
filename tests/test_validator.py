from pathlib import Path

from osi_core.serializer import load_osi_yaml
from osi_core.validator import validate_schema


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_tpcds_example_passes_validation():
    model = load_osi_yaml(FIXTURE_DIR / "tpcds_semantic_model.yaml")
    errors = validate_schema(model)
    assert errors == []


def test_missing_version_detected():
    errors = validate_schema({"semantic_model": []})
    assert any("version" in error.lower() or "schema" in error.lower()
               for error in errors)


def test_duplicate_dataset_names_detected():
    model = {
        "version": "0.1.1",
        "semantic_model": [
            {
                "name": "test-model",
                "datasets": [
                    {"name": "orders", "fields": []},
                    {"name": "orders", "fields": []},
                ],
            }
        ],
    }
    errors = validate_schema(model)
    assert any("duplicate dataset name" in error.lower() for error in errors)


def test_invalid_relationship_references():
    model = {
        "version": "0.1.1",
        "semantic_model": [
            {
                "name": "test-model",
                "datasets": [
                    {"name": "orders", "fields": [
                        {"name": "id", "expression": "id"}]},
                ],
                "relationships": [
                    {
                        "name": "bad_rel",
                        "from": "orders",
                        "to": "customers",
                        "from_columns": ["customer_id"],
                        "to_columns": ["id"],
                    }
                ],
            }
        ],
    }
    errors = validate_schema(model)
    assert any("unknown to dataset" in error.lower() for error in errors)


def test_invalid_sql_expression_detected():
    model = {
        "version": "0.1.1",
        "semantic_model": [
            {
                "name": "test-model",
                "datasets": [
                    {
                        "name": "orders",
                        "fields": [
                            {
                                "name": "bad_field",
                                "expression": {
                                    "dialects": [
                                        {"dialect": "ANSI_SQL",
                                            "expression": "SELECT FROM"}
                                    ]
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }
    errors = validate_schema(model)
    assert any("sql parse error" in error.lower() for error in errors)
