"""Load declarative process configs from configs/processes/*.json."""

from __future__ import annotations

import json
from pathlib import Path

from .process_models import (
    BottleneckSeverity,
    EntityInvolvement,
    ProcessConfig,
    StageConfig,
    StageMetrics,
    StageType,
)


CONFIGS_DIR = Path(__file__).parent.parent.parent / "configs" / "processes"


def _build_stage(stage_data: dict, sla_target: float, sm: dict) -> StageConfig:
    entities = [
        EntityInvolvement(
            api_name=e["api_name"],
            label=e["api_name"].removeprefix("LLC_BI__").removesuffix("__c").replace("_", " "),
            role=e["role"],
            relevant_fields=e.get("relevant_fields", []),
        )
        for e in stage_data.get("involved_entities", [])
    ]

    return StageConfig(
        name=stage_data["name"],
        stage_key=stage_data["stage_key"],
        order=stage_data["order"],
        stage_type=StageType(stage_data["stage_type"]),
        description=stage_data.get("description", ""),
        metrics=StageMetrics(
            avg_days=sm.get("avg_days", 0),
            p50_days=sm.get("p50_days", 0),
            p90_days=sm.get("p90_days", 0),
            entry_count=sm.get("entry_count", 0),
            exit_count=sm.get("exit_count", 0),
            error_rate=sm.get("error_rate", 0),
            rework_rate=sm.get("rework_rate", 0),
            sla_target_days=sla_target,
            sla_met_pct=sm.get("sla_met_pct", 0),
            bottleneck_severity=BottleneckSeverity(sm.get("bottleneck_severity", "none")),
        ),
        involved_entities=entities,
        predecessors=stage_data.get("predecessors", []),
        successors=stage_data.get("successors", []),
    )


def load_process_config(path: Path) -> ProcessConfig:
    data = json.loads(path.read_text(encoding="utf-8"))

    stages: list[StageConfig] = []
    for stage_data in data["stages"]:
        sla = stage_data.get("sla_target_days", 0)
        sm = stage_data.get("synthetic_metrics", {})
        stages.append(_build_stage(stage_data, sla, sm))

    return ProcessConfig(
        name=data["name"],
        process_key=data["process_key"],
        description=data.get("description", ""),
        domain=data.get("domain", data["process_key"]),
        source_object=data["source_object"],
        stage_field=data["stage_field"],
        stages=stages,
    )


def load_all_process_configs(configs_dir: Path | None = None) -> dict[str, ProcessConfig]:
    directory = configs_dir or CONFIGS_DIR
    if not directory.exists():
        raise FileNotFoundError(
            f"Process config directory not found: {directory}. "
            f"Create configs/processes/*.json to define processes."
        )

    configs: dict[str, ProcessConfig] = {}
    json_files = sorted(directory.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(
            f"No process config files found in {directory}. "
            f"Add at least one .json config file."
        )

    for path in json_files:
        cfg = load_process_config(path)
        configs[cfg.process_key] = cfg
    return configs
