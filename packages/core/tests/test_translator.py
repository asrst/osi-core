import pytest
from osi_core.translator import Translator
from osi_core.adapters import OsiAdapter, MetricFlowAdapter
from osi_core.models import ResolvedModel, SemanticModel, Dataset, Field, Metric
from osi_core.models.types import DialectExpr, DialectExpression, Dialect


class DummyAdapter:
    format_name = "dummy"

    def parse(self, source, version=None):
        from osi_core.models import Dataset, Field, Metric
        from osi_core.models.types import ParseResult, DialectExpr, DialectExpression, Dialect
        return ParseResult(
            raw={
                "semantic_model": [
                    {
                        "name": "dummy",
                        "datasets": [
                            Dataset(
                                name="test",
                                source="test.src",
                                fields=[
                                    Field(
                                        name="id",
                                        expression=DialectExpression(dialects=[
                                            DialectExpr(dialect=Dialect.ANSI_SQL, expression="id")
                                        ])
                                    )
                                ]
                            )
                        ],
                        "relationships": [],
                        "metrics": [
                            Metric(
                                name="test_metric",
                                expression=DialectExpression(dialects=[
                                    DialectExpr(dialect=Dialect.ANSI_SQL, expression="COUNT(*)")
                                ])
                            )
                        ]
                    }
                ],
                "version": "0.1.1"
            },
            source_format='dummy',
            source_version='1.0',
            custom_extensions=[],
            osi_spec_version='0.1.1',
        )

    def translate(self, model, target_version=None):
        return f"dummy_output_{model.name}"


class TestTranslator:
    def test_init_with_adapters_dict(self):
        adapters = {"osi": OsiAdapter(), "dummy": DummyAdapter()}
        translator = Translator(adapters)
        assert translator.adapters == adapters

    def test_translate_osi_to_osi(self):
        adapters = {"osi": OsiAdapter()}
        translator = Translator(adapters)

        input_yaml = """
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
      - name: user_count
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: COUNT(*)
    relationships: []
"""
        result = translator.translate(input_yaml, "osi", "osi")
        assert "test_model" in result
        assert "version:" in result
        assert "semantic_model:" in result

    def test_translate_with_input_version(self):
        adapters = {"osi": OsiAdapter()}
        translator = Translator(adapters)

        input_yaml = """
name: legacy_model
datasets:
  - name: users
    fields:
      - name: id
        type: integer
metrics:
  - name: user_count
    expression: COUNT(*)
"""
        result = translator.translate(input_yaml, "osi", "osi", input_version="legacy")
        assert "version:" in result
        assert "semantic_model:" in result

    def test_translate_unknown_from_format(self):
        adapters = {"osi": OsiAdapter()}
        translator = Translator(adapters)

        with pytest.raises(KeyError):
            translator.translate("source", "unknown", "osi")

    def test_translate_unknown_to_format(self):
        adapters = {"osi": OsiAdapter()}
        translator = Translator(adapters)

        with pytest.raises(KeyError):
            translator.translate("source", "osi", "unknown")

    def test_parse_to_model(self):
        adapters = {"osi": OsiAdapter()}
        translator = Translator(adapters)

        input_yaml = """
version: "0.1.1"
semantic_model:
  - name: test_model
    datasets: []
    metrics: []
    relationships: []
"""
        model = translator.parse_to_model(input_yaml, "osi")
        assert isinstance(model, ResolvedModel)
        assert model.name == "test_model"
        assert model.osi_spec_version == "0.1.1"

    def test_parse_to_model_unknown_format(self):
        adapters = {"osi": OsiAdapter()}
        translator = Translator(adapters)

        with pytest.raises(KeyError):
            translator.parse_to_model("source", "unknown")