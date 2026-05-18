"""Process bottleneck query engine — reads process markdown files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .frontmatter import parse_frontmatter
from .process_index import ProcessIndex
from .reader import VaultReader


@dataclass
class StageResult:
    name: str
    order: int
    stage_type: str
    avg_days: float
    p50_days: float
    p90_days: float
    entry_count: int
    exit_count: int
    drop_off_pct: float
    error_rate: float
    rework_rate: float
    sla_target_days: float
    sla_met_pct: float
    is_bottleneck: bool
    bottleneck_severity: str
    entities: list[str] = field(default_factory=list)
    next_stages: list[str] = field(default_factory=list)


@dataclass
class BottleneckResult:
    stage_name: str
    severity: str
    reason: str
    p90_days: float
    sla_target_days: float
    sla_met_pct: float
    error_rate: float
    entities: list[str] = field(default_factory=list)


@dataclass
class ProcessResult:
    name: str
    label: str
    domain: str
    total_stages: int
    cycle_time_days: float
    throughput: int
    stages: list[StageResult] = field(default_factory=list)
    bottlenecks: list[BottleneckResult] = field(default_factory=list)


_STAGE_HEADER = re.compile(r"^###\s+Stage\s+(\d+):\s+(.+?)(?:\s+\(.*\))?\s*(?:[🔴🟠🟢]\s*)?(?:\*\*.*\*\*)?$")
_METRIC_ROW = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|$")
_ENTITY_LINE = re.compile(r"^-\s+\[\[(.+?)\]\]\s+\(`(.+?)`\)")
_FLOW_LINE = re.compile(r"^\*\*Flow:\*\*\s+(.+?)→\s+\*\*.*?\*\*\s+→\s+(.+)$")


def _parse_float(s: str) -> float:
    m = re.search(r"[\d.]+", s)
    return float(m.group()) if m else 0.0


def _parse_int(s: str) -> int:
    m = re.search(r"\d+", s)
    return int(m.group()) if m else 0


def _parse_pct(s: str) -> float:
    m = re.search(r"(\d+)", s)
    return int(m.group()) / 100.0 if m else 0.0


class ProcessSearch:
    def __init__(self, reader: VaultReader) -> None:
        self._reader = reader
        self._index = ProcessIndex(reader)
        self._cache: dict[str, tuple[dict, str]] = {}

    def _read_process(self, name: str) -> tuple[dict, str] | None:
        if name in self._cache:
            return self._cache[name]
        entry = self._index.get(name)
        if not entry:
            return None
        try:
            raw = self._reader.read_file(entry.file)
        except (FileNotFoundError, OSError):
            return None
        result = parse_frontmatter(raw)
        self._cache[name] = result
        return result

    def _parse_stages(self, body: str) -> list[StageResult]:
        stages: list[StageResult] = []
        sections = re.split(r"(?=^### Stage \d+:)", body, flags=re.MULTILINE)

        for section in sections:
            header_match = _STAGE_HEADER.match(section.strip().split("\n")[0] if section.strip() else "")
            if not header_match:
                continue

            order = int(header_match.group(1))
            name = header_match.group(2).strip()

            metrics: dict[str, str] = {}
            entities: list[str] = []
            next_stages: list[str] = []
            stage_type = "sequential"

            for line in section.split("\n"):
                row = _METRIC_ROW.match(line)
                if row and row.group(1).strip() not in ("Metric",):
                    metrics[row.group(1).strip()] = row.group(2).strip()

                ent = _ENTITY_LINE.match(line)
                if ent:
                    entities.append(ent.group(1))

                flow = _FLOW_LINE.match(line)
                if flow:
                    raw_succ = flow.group(2).strip()
                    if raw_succ and raw_succ != "—":
                        next_stages = [s.strip() for s in raw_succ.split(",")]

            if "(parallel)" in section.split("\n")[0].lower():
                stage_type = "parallel"
            elif "(post_close)" in section.split("\n")[0].lower():
                stage_type = "post_close"

            sev = metrics.get("Bottleneck Severity", "NONE").lower()
            is_bn = sev in ("high", "critical")

            stages.append(StageResult(
                name=name,
                order=order,
                stage_type=stage_type,
                avg_days=_parse_float(metrics.get("Avg Duration", "0")),
                p50_days=_parse_float(metrics.get("P50 Duration", "0")),
                p90_days=_parse_float(metrics.get("P90 Duration", "0")),
                entry_count=_parse_int(metrics.get("Entry Count", "0")),
                exit_count=_parse_int(metrics.get("Exit Count", "0")),
                drop_off_pct=_parse_pct(metrics.get("Drop-off Rate", "0%")),
                error_rate=_parse_pct(metrics.get("Error Rate", "0%")),
                rework_rate=_parse_pct(metrics.get("Rework Rate", "0%")),
                sla_target_days=_parse_float(metrics.get("SLA Target", "0")),
                sla_met_pct=_parse_pct(metrics.get("SLA Met", "0%")),
                is_bottleneck=is_bn,
                bottleneck_severity=sev,
                entities=entities,
                next_stages=next_stages,
            ))

        return sorted(stages, key=lambda s: s.order)

    def list_processes(self, domain: str | None = None) -> list[dict]:
        entries = self._index.list_all(domain)
        return [
            {
                "name": e.name,
                "label": e.label,
                "domain": e.domain,
                "stage_count": e.stage_count,
                "cycle_time_days": e.cycle_time_days,
                "throughput": e.throughput,
                "bottleneck_severity": e.bottleneck_severity,
            }
            for e in entries
        ]

    def get_process(self, name: str) -> ProcessResult | None:
        data = self._read_process(name)
        if not data:
            return None
        fm, body = data
        stages = self._parse_stages(body)
        bottlenecks = self._build_bottlenecks(stages)
        return ProcessResult(
            name=name,
            label=fm.get("label", name),
            domain=fm.get("domain", ""),
            total_stages=len(stages),
            cycle_time_days=fm.get("total_cycle_time_days", 0),
            throughput=fm.get("throughput_per_month", 0),
            stages=stages,
            bottlenecks=bottlenecks,
        )

    def get_bottlenecks(self, process_name: str) -> list[BottleneckResult]:
        data = self._read_process(process_name)
        if not data:
            return []
        _, body = data
        stages = self._parse_stages(body)
        return self._build_bottlenecks(stages)

    def _build_bottlenecks(self, stages: list[StageResult]) -> list[BottleneckResult]:
        results: list[BottleneckResult] = []
        severity_order = {"critical": 0, "high": 1, "medium": 2}
        for s in stages:
            if s.bottleneck_severity not in ("high", "critical"):
                continue
            reasons: list[str] = []
            if s.sla_target_days > 0:
                ratio = s.p90_days / s.sla_target_days
                if ratio > 1.5:
                    reasons.append(f"P90 ({s.p90_days}d) exceeds SLA ({s.sla_target_days}d) by {ratio:.1f}x")
            if s.sla_met_pct < 0.75:
                reasons.append(f"SLA compliance only {s.sla_met_pct * 100:.0f}%")
            if s.error_rate > 0.10:
                reasons.append(f"Error rate {s.error_rate * 100:.0f}%")
            if s.rework_rate > 0.08:
                reasons.append(f"Rework rate {s.rework_rate * 100:.0f}%")

            results.append(BottleneckResult(
                stage_name=s.name,
                severity=s.bottleneck_severity,
                reason="; ".join(reasons) if reasons else "Multiple SLA indicators exceeded",
                p90_days=s.p90_days,
                sla_target_days=s.sla_target_days,
                sla_met_pct=s.sla_met_pct,
                error_rate=s.error_rate,
                entities=s.entities,
            ))
        results.sort(key=lambda b: severity_order.get(b.severity, 99))
        return results

    def get_stage(self, process_name: str, stage_name: str) -> StageResult | None:
        data = self._read_process(process_name)
        if not data:
            return None
        _, body = data
        stages = self._parse_stages(body)
        stage_lower = stage_name.lower()
        for s in stages:
            if s.name.lower() == stage_lower:
                return s
        return None

    def get_process_flow(self, process_name: str) -> list[StageResult] | None:
        data = self._read_process(process_name)
        if not data:
            return None
        _, body = data
        return self._parse_stages(body)

    def get_entity_stages(self, entity_name: str) -> list[dict]:
        results: list[dict] = []
        for proc_name in self._index.list_all():
            data = self._read_process(proc_name.name)
            if not data:
                continue
            _, body = data
            stages = self._parse_stages(body)
            name_lower = entity_name.lower()
            for s in stages:
                if any(e.lower() == name_lower for e in s.entities):
                    results.append({
                        "process": proc_name.name,
                        "process_label": proc_name.label,
                        "stage": s.name,
                        "stage_order": s.order,
                    })
        return results
