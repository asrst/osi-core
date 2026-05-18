from typing import Any, Dict, List

from .models import ResolvedModel, Metric, SemanticModel, Dataset


class DiffResult:
    def __init__(self):
        self.added_metrics: List[Metric] = []
        self.removed_metrics: List[Metric] = []
        self.changed_metrics: List[Dict[str, Any]] = []
        self.added_datasets: List[Dataset] = []
        self.removed_datasets: List[Dataset] = []
        self.breaking_changes: bool = False

    def has_changes(self) -> bool:
        return bool(
            self.added_metrics
            or self.removed_metrics
            or self.changed_metrics
            or self.added_datasets
            or self.removed_datasets
        )


class ModelDiff:
    def compare(self, old: ResolvedModel, new: ResolvedModel) -> DiffResult:
        result = DiffResult()

        old_sms = {sm.name: sm for sm in old.semantic_models}
        new_sms = {sm.name: sm for sm in new.semantic_models}

        for sm_name, new_sm in new_sms.items():
            if sm_name not in old_sms:
                for ds in new_sm.datasets:
                    result.added_datasets.append(ds)
                for m in new_sm.metrics:
                    result.added_metrics.append(m)

        for sm_name, old_sm in old_sms.items():
            if sm_name not in new_sms:
                for ds in old_sm.datasets:
                    result.removed_datasets.append(ds)
                for m in old_sm.metrics:
                    result.removed_metrics.append(m)

        for sm_name in set(old_sms.keys()) & set(new_sms.keys()):
            old_sm = old_sms[sm_name]
            new_sm = new_sms[sm_name]

            old_ds_names = {ds.name for ds in old_sm.datasets}
            new_ds_names = {ds.name for ds in new_sm.datasets}
            result.added_datasets.extend(
                ds for ds in new_sm.datasets if ds.name not in old_ds_names
            )
            result.removed_datasets.extend(
                ds for ds in old_sm.datasets if ds.name not in new_ds_names
            )

            old_metrics = {m.name: m for m in old_sm.metrics}
            new_metrics = {m.name: m for m in new_sm.metrics}

            for name, new_m in new_metrics.items():
                if name not in old_metrics:
                    result.added_metrics.append(new_m)
                else:
                    old_m = old_metrics[name]
                    if self._metric_changed(old_m, new_m):
                        result.changed_metrics.append({'id': name, 'old': old_m, 'new': new_m})

            for name, old_m in old_metrics.items():
                if name not in new_metrics:
                    result.removed_metrics.append(old_m)

        if result.removed_metrics or result.changed_metrics:
            result.breaking_changes = True

        return result

    def _metric_changed(self, old: Metric, new: Metric) -> bool:
        old_expr = old.expression.dialects[0].expression if old.expression.dialects else ""
        new_expr = new.expression.dialects[0].expression if new.expression.dialects else ""
        return old_expr != new_expr or old.description != new.description