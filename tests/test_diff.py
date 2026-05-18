import pytest
from osi_core.models import OsiModel, SemanticModel, Dataset, Field, Metric
from osi_core.models.types import DialectExpr, DialectExpression, Dialect
from osi_core.diff import ModelDiff, DiffResult


class TestModelDiff:
    def _make_model(self, name, ds_names, metric_names):
        datasets = []
        for ds_name in ds_names:
            ds = Dataset(
                name=ds_name,
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
            datasets.append(ds)

        metrics = []
        for m_name in metric_names:
            metrics.append(Metric(
                name=m_name,
                expression=DialectExpression(dialects=[
                    DialectExpr(dialect=Dialect.ANSI_SQL, expression="COUNT(*)")
                ])
            ))

        sm = SemanticModel(
            name=name,
            datasets=datasets,
            metrics=metrics,
            relationships=[],
        )
        return OsiModel(
            name=name,
            semantic_models=[sm],
        )

    def test_no_changes(self):
        model = self._make_model("test", ["users"], ["total"])
        differ = ModelDiff()
        result = differ.compare(model, model)
        assert not result.has_changes()

    def test_detects_added_metric(self):
        old = self._make_model("test", ["users"], ["total"])
        new = self._make_model("test", ["users"], ["total", "count"])
        differ = ModelDiff()
        result = differ.compare(old, new)
        assert result.has_changes()
        assert len(result.added_metrics) == 1
        assert result.added_metrics[0].name == "count"

    def test_detects_removed_metric(self):
        old = self._make_model("test", ["users"], ["total", "count"])
        new = self._make_model("test", ["users"], ["total"])
        differ = ModelDiff()
        result = differ.compare(old, new)
        assert result.has_changes()
        assert len(result.removed_metrics) == 1
        assert result.removed_metrics[0].name == "count"

    def test_detects_changed_metric_expression(self):
        old = self._make_model("test", ["users"], ["total"])
        new = self._make_model("test", ["users"], ["total"])

        old_expr = DialectExpression(dialects=[
            DialectExpr(dialect=Dialect.ANSI_SQL, expression="COUNT(*)")
        ])
        new_expr = DialectExpression(dialects=[
            DialectExpr(dialect=Dialect.ANSI_SQL, expression="SUM(amount)")
        ])
        old.semantic_models[0].metrics[0].expression = old_expr
        new.semantic_models[0].metrics[0].expression = new_expr

        differ = ModelDiff()
        result = differ.compare(old, new)
        assert result.has_changes()
        assert len(result.changed_metrics) == 1

    def test_detects_added_dataset(self):
        old = self._make_model("test", ["users"], ["total"])
        new = self._make_model("test", ["users", "orders"], ["total"])
        differ = ModelDiff()
        result = differ.compare(old, new)
        assert result.has_changes()
        assert len(result.added_datasets) == 1
        assert result.added_datasets[0].name == "orders"

    def test_detects_breaking_changes(self):
        old = self._make_model("test", ["users"], ["total", "count"])
        new = self._make_model("test", ["users"], ["total"])
        differ = ModelDiff()
        result = differ.compare(old, new)
        assert result.breaking_changes is True

    def test_no_breaking_changes_on_additions(self):
        old = self._make_model("test", ["users"], ["total"])
        new = self._make_model("test", ["users", "orders"], ["total", "count"])
        differ = ModelDiff()
        result = differ.compare(old, new)
        assert result.breaking_changes is False