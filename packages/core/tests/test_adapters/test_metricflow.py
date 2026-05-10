import pytest
from pathlib import Path
from osi_core.adapters import MetricFlowAdapter
from osi_core.resolver import resolve


class TestMetricFlowAdapter:
    @pytest.fixture
    def sample_file(self):
        return (
            Path(__file__).parent.parent
            / "fixtures"
            / "metricflow"
            / "sample.yaml"
        )

    @pytest.fixture
    def adapter(self):
        return MetricFlowAdapter()

    def test_format_name(self, adapter):
        assert adapter.format_name == "metricflow"

    def test_parse_yaml_file(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        assert result.source_format == "metricflow"
        assert result.raw is not None

    def test_parse_version(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        assert result.source_version == "1.0"

    def test_resolve_model(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        from osi_core.models import ResolvedModel
        model = resolve(result)
        assert isinstance(model, ResolvedModel)
        assert model.name == "analytics_model"

    def test_resolve_datasets_from_semantic_model(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        assert len(model.semantic_models) > 0
        sm = model.semantic_models[0]
        assert len(sm.datasets) > 0

    def test_resolve_metrics(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        sm = model.semantic_models[0]
        metric_names = {m.name for m in sm.metrics}
        assert "total_revenue" in metric_names

    def test_translate_produces_metricflow_yaml(self, adapter, sample_file):
        result = adapter.parse(sample_file)
        model = resolve(result)
        output = adapter.translate(model)

        import yaml
        data = yaml.safe_load(output)
        assert data["name"] == "analytics_model"
        assert "semantic_model" in data
        assert "metrics" in data

    def test_translate_roundtrip(self, adapter, sample_file):
        result1 = adapter.parse(sample_file)
        model = resolve(result1)
        output = adapter.translate(model)

        result2 = adapter.parse(output)
        model2 = resolve(result2)

        assert model.name == model2.name
        sm1 = model.semantic_models[0]
        sm2 = model2.semantic_models[0]
        assert len(sm1.datasets) == len(sm2.datasets)
        assert len(sm1.metrics) == len(sm2.metrics)