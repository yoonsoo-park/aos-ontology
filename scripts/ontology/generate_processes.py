"""Generate process bottleneck analysis notes for the ontology vault."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .process_config_loader import load_all_process_configs
from .process_models import (
    BottleneckSeverity,
    ProcessConfig,
    StageConfig,
    StageType,
)


_RED = "🔴"
_ORANGE = "🟠"
_GREEN = "🟢"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _severity_label(s: BottleneckSeverity) -> str:
    return s.value.upper()


def _generate_process_note(process: ProcessConfig) -> str:
    seq = process.sequential_stages
    bottlenecks = process.bottleneck_stages
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Frontmatter ---
    fm_lines = [
        "---",
        f"process_id: {process.process_key}",
        f"label: {process.name}",
        f"domain: {process.domain}",
        f"source_entity: {process.source_object}",
        f"stage_field: {process.stage_field}",
        f"total_stages: {len(process.stages)}",
        f"total_cycle_time_days: {process.total_cycle_time_days}",
        f"throughput_per_month: {process.throughput}",
        f'measurement_period: "2025-Q4"',
        f"data_source: synthetic",
    ]
    if bottlenecks:
        fm_lines.append("top_bottlenecks:")
        for b in bottlenecks:
            fm_lines.append(f"  - stage: {b.name}")
            fm_lines.append(f"    severity: {b.metrics.bottleneck_severity.value}")
            fm_lines.append(f"    avg_days: {int(b.metrics.avg_days)}")
    fm_lines.append(f"tags: [process, {process.process_key}]")
    fm_lines.append(f'generated_at: "{now}"')
    fm_lines.append("---")

    sections: list[str] = ["\n".join(fm_lines), ""]

    # --- Title + Description ---
    sections.append(f"# {process.name} Process\n")
    sections.append(f"{process.description}\n")

    # --- How to Read This ---
    sections.append("> **How to read this note:** The flow diagram below shows every stage a loan passes through. ")
    sections.append(f"> **{_RED} Red** = critical slowdown, **{_ORANGE} Orange** = significant delay, **{_GREEN} Green** = on track. ")
    sections.append("> Numbers on arrows = loans passing between stages. Click any stage heading to see details.\n")

    # --- Interactive Flow (ontology-flow plugin) ---
    sections.append("```ontology-flow")
    sections.append(f"process: {process.process_key}")
    sections.append("layout: LR")
    sections.append("highlight: bottlenecks")
    sections.append("```\n")

    # --- Process Summary ---
    initial = seq[0].metrics.entry_count if seq else 0
    final = process.throughput
    conv = f"{final / initial * 100:.1f}%" if initial else "N/A"
    sections.append("## Process Summary\n")
    sections.append("| Metric | Value |")
    sections.append("|--------|-------|")
    par = [s for s in process.stages if s.stage_type == StageType.PARALLEL]
    pc = [s for s in process.stages if s.stage_type == StageType.POST_CLOSE]
    sections.append(f"| Total Stages | {len(process.stages)} ({len(seq)} main + {len(par)} support + {len(pc)} post-close) |")
    sections.append(f"| Avg Time to Close | {process.total_cycle_time_days} days |")
    sections.append(f"| Loans Entering / Month | {initial:,} |")
    sections.append(f"| Loans Completed / Month | {final:,} |")
    sections.append(f"| Completion Rate | {conv} |")
    sections.append(f"| Stages with Delays | {len(bottlenecks)} |")
    sections.append(f"| Data Source | synthetic (benchmark-based) |")
    sections.append("")

    # --- Bottleneck Analysis ---
    if bottlenecks:
        sections.append("## Where Loans Get Stuck\n")
        sections.append(f"These {len(bottlenecks)} stages consistently take longer than expected and cause delays downstream.\n")
        for i, stage in enumerate(bottlenecks, 1):
            m = stage.metrics
            sla_ratio = m.p90_days / m.sla_target_days if m.sla_target_days > 0 else 0
            sev_icon = _RED if m.bottleneck_severity == BottleneckSeverity.CRITICAL else _ORANGE
            entities = ", ".join(f"[[{e.label}]]" for e in stage.involved_entities)
            sections.append(f"### {sev_icon} {i}. {stage.name}\n")
            sections.append(f"- **Worst-case duration:** {m.p90_days} days (target: {m.sla_target_days} days) — {sla_ratio:.1f}x over target")
            sections.append(f"- **On-time rate:** {_fmt_pct(m.sla_met_pct)} of loans meet the target deadline")
            sections.append(f"- **Error rate:** {_fmt_pct(m.error_rate)} of loans have errors at this stage")
            sections.append(f"- **Rework rate:** {_fmt_pct(m.rework_rate)} need to be sent back for corrections")
            sections.append(f"- **Data objects involved:** {entities}")
            sections.append(f"- **Why it matters:** {stage.description}")
            sections.append("")
            sections.append("```chart")
            sections.append("type: bar")
            sections.append("labels: [P50, Avg, P90, SLA Target]")
            sections.append("series:")
            sections.append(f"  - title: Days")
            sections.append(f"    data: [{m.p50_days}, {int(m.avg_days)}, {m.p90_days}, {m.sla_target_days}]")
            sections.append("width: 80%")
            sections.append("labelColors: true")
            sections.append("```")
            sections.append("")

    # --- Stages ---
    sections.append("## All Stages\n")
    for stage in process.stages:
        m = stage.metrics
        type_tag = f" *(support stage)*" if stage.stage_type == StageType.PARALLEL else (f" *(post-close)*" if stage.stage_type == StageType.POST_CLOSE else "")
        if m.bottleneck_severity == BottleneckSeverity.CRITICAL:
            bn_tag = f" {_RED} **CRITICAL DELAY**"
        elif m.bottleneck_severity == BottleneckSeverity.HIGH:
            bn_tag = f" {_ORANGE} **SIGNIFICANT DELAY**"
        else:
            bn_tag = ""
        sections.append(f"### Stage {stage.order}: {stage.name}{type_tag}{bn_tag}\n")
        sections.append(f"{stage.description}\n")

        sections.append("| Metric | Value |")
        sections.append("|--------|-------|")
        sections.append(f"| Avg Duration | {m.avg_days} days |")
        sections.append(f"| P50 Duration | {m.p50_days} days |")
        sections.append(f"| P90 Duration | {m.p90_days} days |")
        sections.append(f"| Entry Count | {m.entry_count:,} |")
        sections.append(f"| Exit Count | {m.exit_count:,} |")
        sections.append(f"| Drop-off Rate | {_fmt_pct(m.drop_off_rate)} |")
        sections.append(f"| Error Rate | {_fmt_pct(m.error_rate)} |")
        sections.append(f"| Rework Rate | {_fmt_pct(m.rework_rate)} |")
        sections.append(f"| SLA Target | {m.sla_target_days} days |")
        sections.append(f"| SLA Met | {_fmt_pct(m.sla_met_pct)} |")
        sections.append(f"| Bottleneck Severity | {_severity_label(m.bottleneck_severity)} |")
        sections.append("")

        if stage.involved_entities:
            sections.append("**Data Objects Used:**\n")
            for e in stage.involved_entities:
                fields = ", ".join(f"`{f}`" for f in e.relevant_fields) if e.relevant_fields else "—"
                sections.append(f"- [[{e.label}]] (`{e.api_name}`) — {e.role}: {fields}")
            sections.append("")

        if stage.predecessors or stage.successors:
            pred = ", ".join(stage.predecessors) if stage.predecessors else "start"
            succ = ", ".join(stage.successors) if stage.successors else "end"
            sections.append(f"**Flow:** {pred} → **{stage.name}** → {succ}\n")

    # --- Process Flow ---
    sections.append("## Process Flow\n")
    sections.append("> **Legend:** {0} = critical delay, {1} = significant delay, {2} = on track. Dashed boxes = support stages running in parallel.\n".format(_RED, _ORANGE, _GREEN))
    sections.append("```mermaid")
    sections.append("graph LR")
    for stage in seq:
        node_id = stage.stage_key.replace("_", "")
        label = stage.name
        m = stage.metrics
        if m.bottleneck_severity == BottleneckSeverity.CRITICAL:
            sections.append(f"    {node_id}[\"{_RED} {label}<br/>{m.avg_days}d avg\"]:::critical")
        elif m.bottleneck_severity == BottleneckSeverity.HIGH:
            sections.append(f"    {node_id}[\"{_ORANGE} {label}<br/>{m.avg_days}d avg\"]:::high")
        else:
            sections.append(f"    {node_id}[\"{label}<br/>{m.avg_days}d avg\"]")
    for stage in seq:
        src = stage.stage_key.replace("_", "")
        for succ_key in stage.successors:
            tgt = succ_key.replace("_", "")
            sections.append(f"    {src} -->|{stage.metrics.exit_count}| {tgt}")
    parallel = [s for s in process.stages if s.stage_type == StageType.PARALLEL]
    for stage in parallel:
        node_id = stage.stage_key.replace("_", "")
        sections.append(f"    {node_id}[\"{stage.name}\"]:::parallel")
        for succ_key in stage.successors:
            tgt = succ_key.replace("_", "")
            sections.append(f"    {node_id} -.-> {tgt}")
    sections.append("    classDef critical fill:#7f1d1d,stroke:#ef4444,color:#fca5a5")
    sections.append("    classDef high fill:#7c2d12,stroke:#f97316,color:#fdba74")
    if parallel:
        sections.append("    classDef parallel stroke-dasharray: 5 5")
    sections.append("```\n")

    # --- Entity Participation (Dataview) ---
    sections.append("## Entity Participation\n")
    sections.append("```dataview")
    sections.append("TABLE")
    sections.append('  domain AS "Domain",')
    sections.append('  relationships_out AS "Parents",')
    sections.append('  relationships_in AS "Children",')
    sections.append('  field_count AS "Fields"')
    sections.append('FROM "entities"')
    involved_labels = set()
    for stage in process.stages:
        for e in stage.involved_entities:
            involved_labels.add(e.label)
    if involved_labels:
        conditions = " OR ".join(f'contains(file.name, "{lbl}")' for lbl in sorted(involved_labels))
        sections.append(f"WHERE {conditions}")
    sections.append("SORT relationships_in DESC")
    sections.append("```\n")

    # --- Data Provenance ---
    sections.append("## Data Provenance\n")
    sections.append("- **Source:** Synthetic data based on nCino LLC_BI__Stage__c picklist values and commercial lending benchmarks")
    sections.append("- **Methodology:** Duration distributions modeled on mid-market commercial loans ($1M–$25M)")
    sections.append("- **Replacement Path:** Connect to Salesforce Opportunity History (LLC_BI__Previous_Stage_Duration_Minutes__c) for real stage transition data")
    sections.append("")

    return "\n".join(sections)


_S_HIGH_CRIT = (BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL)


def _generate_process_index(processes: dict[str, ProcessConfig]) -> str:
    index: dict[str, dict] = {}
    for key, proc in processes.items():
        entity_map: dict[str, list[str]] = {}
        for stage in proc.stages:
            for ent in stage.involved_entities:
                entity_map.setdefault(ent.api_name, []).append(stage.stage_key)
        bottlenecks = proc.bottleneck_stages

        stages_data = []
        for stage in proc.stages:
            m = stage.metrics
            stages_data.append({
                "stage_key": stage.stage_key,
                "name": stage.name,
                "order": stage.order,
                "type": stage.stage_type.value,
                "severity": m.bottleneck_severity.value,
                "avg_days": round(m.avg_days, 1),
                "p90_days": m.p90_days,
                "sla_target_days": m.sla_target_days,
                "sla_met_pct": round(m.sla_met_pct * 100),
                "error_rate": round(m.error_rate * 100),
                "entry_count": m.entry_count,
                "exit_count": m.exit_count,
                "predecessors": stage.predecessors,
                "successors": stage.successors,
                "entities": [e.label for e in stage.involved_entities],
            })

        index[key] = {
            "label": proc.name,
            "file": f"processes/{key}.md",
            "domain": proc.domain,
            "total_stages": len(proc.stages),
            "total_cycle_time_days": proc.total_cycle_time_days,
            "throughput_per_month": proc.throughput,
            "top_bottleneck_severity": bottlenecks[0].metrics.bottleneck_severity.value if bottlenecks else "none",
            "bottleneck_stages": [s.name for s in bottlenecks],
            "entity_participation": entity_map,
            "stages": stages_data,
        }
    return json.dumps(index, indent=2, ensure_ascii=False)


def write_processes(
    output_dir: Path,
    processes: dict[str, ProcessConfig] | None = None,
) -> dict[str, int]:
    if processes is None:
        processes = load_all_process_configs()

    processes_dir = output_dir / "processes"
    meta_dir = output_dir / "_meta"
    processes_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    stats = {"processes": 0, "stages": 0}
    for key, proc in processes.items():
        note = _generate_process_note(proc)
        filepath = processes_dir / f"{key}.md"
        filepath.write_text(note, encoding="utf-8")
        stats["processes"] += 1
        stats["stages"] += len(proc.stages)

    idx = _generate_process_index(processes)
    (meta_dir / "process_index.json").write_text(idx, encoding="utf-8")

    return stats
