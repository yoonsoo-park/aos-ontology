"""Data models for process bottleneck analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BottleneckSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StageType(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    POST_CLOSE = "post_close"


@dataclass
class EntityInvolvement:
    api_name: str
    label: str
    role: str
    relevant_fields: list[str] = field(default_factory=list)


@dataclass
class StageMetrics:
    avg_days: float
    p50_days: float
    p90_days: float
    entry_count: int
    exit_count: int
    error_rate: float
    rework_rate: float
    sla_target_days: float
    sla_met_pct: float
    bottleneck_severity: BottleneckSeverity

    @property
    def drop_off_rate(self) -> float:
        if self.entry_count == 0:
            return 0.0
        return round(1.0 - (self.exit_count / self.entry_count), 3)


@dataclass
class StageConfig:
    name: str
    stage_key: str
    order: int
    stage_type: StageType
    description: str
    metrics: StageMetrics
    involved_entities: list[EntityInvolvement] = field(default_factory=list)
    predecessors: list[str] = field(default_factory=list)
    successors: list[str] = field(default_factory=list)


@dataclass
class ProcessConfig:
    name: str
    process_key: str
    description: str
    domain: str
    source_object: str
    stage_field: str
    stages: list[StageConfig] = field(default_factory=list)

    @property
    def sequential_stages(self) -> list[StageConfig]:
        return [s for s in self.stages if s.stage_type == StageType.SEQUENTIAL]

    @property
    def total_cycle_time_days(self) -> float:
        return round(sum(s.metrics.avg_days for s in self.sequential_stages), 1)

    @property
    def throughput(self) -> int:
        seq = self.sequential_stages
        return seq[-1].metrics.exit_count if seq else 0

    @property
    def bottleneck_stages(self) -> list[StageConfig]:
        return sorted(
            [s for s in self.stages
             if s.metrics.bottleneck_severity in (BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL)],
            key=lambda s: list(BottleneckSeverity).index(s.metrics.bottleneck_severity),
            reverse=True,
        )
