"""Pluggable metrics adapter interface for process stage metrics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageMetricsData:
    process_key: str
    stage_key: str
    avg_days: float
    p50_days: float
    p90_days: float
    entry_count: int
    exit_count: int
    error_rate: float
    rework_rate: float
    sla_target_days: float
    sla_met_pct: float
    bottleneck_severity: str
    measurement_period: str = ""
    sample_size: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "avg_days": self.avg_days,
            "p50_days": self.p50_days,
            "p90_days": self.p90_days,
            "entry_count": self.entry_count,
            "exit_count": self.exit_count,
            "error_rate": self.error_rate,
            "rework_rate": self.rework_rate,
            "sla_target_days": self.sla_target_days,
            "sla_met_pct": self.sla_met_pct,
            "bottleneck_severity": self.bottleneck_severity,
        }
        if self.measurement_period:
            d["measurement_period"] = self.measurement_period
        if self.sample_size:
            d["sample_size"] = self.sample_size
        if self.extra:
            d["extra"] = self.extra
        return d


class MetricsAdapter(ABC):

    @abstractmethod
    def fetch_metrics(self, process_key: str) -> list[StageMetricsData]:
        ...

    @abstractmethod
    def adapter_name(self) -> str:
        ...


class SyntheticMetricsAdapter(MetricsAdapter):
    """Reads synthetic_metrics from process config JSON stages."""

    def __init__(self, process_configs: dict[str, Any]) -> None:
        self._configs = process_configs

    def adapter_name(self) -> str:
        return "synthetic"

    def fetch_metrics(self, process_key: str) -> list[StageMetricsData]:
        from .process_models import ProcessConfig

        cfg = self._configs.get(process_key)
        if not cfg:
            return []

        if isinstance(cfg, ProcessConfig):
            return self._from_process_config(process_key, cfg)
        return []

    def _from_process_config(self, process_key: str, cfg: Any) -> list[StageMetricsData]:
        results: list[StageMetricsData] = []
        for stage in cfg.stages:
            m = stage.metrics
            results.append(StageMetricsData(
                process_key=process_key,
                stage_key=stage.stage_key,
                avg_days=m.avg_days,
                p50_days=m.p50_days,
                p90_days=m.p90_days,
                entry_count=m.entry_count,
                exit_count=m.exit_count,
                error_rate=m.error_rate,
                rework_rate=m.rework_rate,
                sla_target_days=m.sla_target_days,
                sla_met_pct=m.sla_met_pct,
                bottleneck_severity=m.bottleneck_severity.value,
                measurement_period="synthetic",
            ))
        return results
