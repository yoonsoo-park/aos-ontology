"""Agent-assisted process config generation using Bedrock Claude."""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from .agent_assist import _call_llm, _extract_json, _entity_summary
from .models import SFObject, SFPicklistValue


@dataclass
class ProcessCandidate:
    source_object: str
    stage_field: str
    picklist_values: list[SFPicklistValue]
    field_description: str = ""
    domain: str = ""


def discover_process_candidates(
    objects: dict[str, SFObject],
    domain_mapping: dict[str, str] | None = None,
) -> list[ProcessCandidate]:
    in_degree: dict[str, int] = {k: 0 for k in objects}
    for obj in objects.values():
        for rel in obj.relationships:
            if rel.target_object in in_degree:
                in_degree[rel.target_object] += 1

    candidates: list[ProcessCandidate] = []
    for api_name, obj in objects.items():
        if in_degree.get(api_name, 0) < 5:
            continue
        for f in obj.fields:
            if f.type != "Picklist":
                continue
            if "stage" not in f.api_name.lower():
                continue
            if len(f.picklist_values) < 4:
                continue
            domain = ""
            if domain_mapping:
                domain = domain_mapping.get(api_name, "")
            candidates.append(ProcessCandidate(
                source_object=api_name,
                stage_field=f.api_name,
                picklist_values=f.picklist_values,
                field_description=f.description,
                domain=domain,
            ))
    return candidates


def _get_related_objects(
    source_object: str,
    objects: dict[str, SFObject],
    max_hops: int = 2,
    max_objects: int = 60,
) -> dict[str, SFObject]:
    if source_object not in objects:
        return {}

    visited: dict[str, int] = {source_object: 0}
    queue: deque[tuple[str, int]] = deque([(source_object, 0)])

    while queue:
        current, depth = queue.popleft()
        if depth >= max_hops:
            continue
        obj = objects.get(current)
        if not obj:
            continue
        for rel in obj.relationships:
            if rel.target_object in objects and rel.target_object not in visited:
                visited[rel.target_object] = depth + 1
                queue.append((rel.target_object, depth + 1))
        for rel in obj.incoming_relationships:
            if rel.source_object in objects and rel.source_object not in visited:
                visited[rel.source_object] = depth + 1
                queue.append((rel.source_object, depth + 1))

    sorted_keys = sorted(visited.keys(), key=lambda k: (visited[k], k))
    selected = sorted_keys[:max_objects]
    return {k: objects[k] for k in selected}


_FEW_SHOT = json.dumps({
    "name": "Loan Origination",
    "process_key": "loan-origination",
    "description": "End-to-end commercial loan origination workflow.",
    "domain": "loan-origination",
    "source_object": "LLC_BI__Loan__c",
    "stage_field": "LLC_BI__Stage__c",
    "metrics_source": "synthetic",
    "stages": [
        {
            "name": "Qualification", "stage_key": "qualification", "order": 1,
            "stage_type": "sequential",
            "description": "Initial borrower qualification and pre-screening",
            "predecessors": [], "successors": ["proposal"],
            "sla_target_days": 2.0,
            "involved_entities": [
                {"api_name": "Account", "role": "primary",
                 "relevant_fields": ["Industry", "BillingState"]},
            ],
            "synthetic_metrics": {
                "avg_days": 1.2, "p50_days": 0.8, "p90_days": 2.5,
                "entry_count": 1000, "exit_count": 600,
                "error_rate": 0.03, "rework_rate": 0.02,
                "sla_met_pct": 0.92, "bottleneck_severity": "none",
            },
        },
        {
            "name": "Credit", "stage_key": "credit", "order": 16,
            "stage_type": "parallel",
            "description": "Parallel credit review support stage",
            "predecessors": [], "successors": ["credit_underwriting"],
            "sla_target_days": 3.0,
            "involved_entities": [
                {"api_name": "LLC_BI__Credit_Memo__c", "role": "primary",
                 "relevant_fields": ["LLC_BI__Description__c"]},
            ],
            "synthetic_metrics": {
                "avg_days": 3.0, "p50_days": 2.0, "p90_days": 6.0,
                "entry_count": 400, "exit_count": 390,
                "error_rate": 0.05, "rework_rate": 0.04,
                "sla_met_pct": 0.80, "bottleneck_severity": "none",
            },
        },
    ],
}, indent=2)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug


def _validate_stage_structure(data: dict, picklist_names: set[str]) -> dict:
    stages = data.get("stages", [])
    stage_keys = {s["stage_key"] for s in stages}
    for stage in stages:
        stage["stage_key"] = _slugify(stage.get("stage_key", stage.get("name", "")))
        if stage.get("stage_type") not in ("sequential", "parallel", "post_close"):
            stage["stage_type"] = "sequential"
        stage["predecessors"] = [p for p in stage.get("predecessors", []) if p in stage_keys]
        stage["successors"] = [s for s in stage.get("successors", []) if s in stage_keys]
    return data


def _validate_entity_involvement(
    involvement: dict[str, list[dict]],
    valid_objects: set[str],
) -> dict[str, list[dict]]:
    cleaned: dict[str, list[dict]] = {}
    for stage_key, entities in involvement.items():
        valid = []
        for ent in entities:
            if ent.get("api_name") not in valid_objects:
                continue
            if ent.get("role") not in ("primary", "reference"):
                ent["role"] = "reference"
            ent["relevant_fields"] = ent.get("relevant_fields", [])[:4]
            valid.append(ent)
        cleaned[stage_key] = valid
    return cleaned


def _validate_metrics(
    metrics: dict[str, dict],
    stage_order: list[str],
) -> dict[str, dict]:
    seq_keys = stage_order
    prev_entry = None

    for key in seq_keys:
        m = metrics.get(key)
        if not m:
            continue
        if m.get("p50_days", 0) > m.get("avg_days", 0):
            m["p50_days"] = m["avg_days"]
        if m.get("avg_days", 0) > m.get("p90_days", 0):
            m["p90_days"] = m["avg_days"]
        if m.get("exit_count", 0) > m.get("entry_count", 0):
            m["exit_count"] = m["entry_count"]
        if prev_entry is not None and m.get("entry_count", 0) > prev_entry:
            m["entry_count"] = prev_entry
            m["exit_count"] = min(m.get("exit_count", 0), m["entry_count"])
        prev_entry = m.get("exit_count", prev_entry)

        sev = m.get("bottleneck_severity", "none")
        if sev not in ("none", "low", "medium", "high", "critical"):
            m["bottleneck_severity"] = "none"

        for rate_key in ("error_rate", "rework_rate", "sla_met_pct"):
            val = m.get(rate_key, 0)
            m[rate_key] = max(0.0, min(1.0, val))

    return metrics


def infer_stage_structure(
    candidate: ProcessCandidate,
    context: str = "",
    model_id: str = "us.anthropic.claude-sonnet-4-6",
) -> dict:
    picklist_list = "\n".join(
        f"  {i+1}. {pv.api_name} (label: {pv.label})"
        for i, pv in enumerate(candidate.picklist_values)
    )

    prompt = f"""You are an expert in financial services workflow design. Given the following picklist values from a Salesforce stage field, determine the correct process flow.

Source Object: {candidate.source_object}
Stage Field: {candidate.stage_field}
{f"Field Description: {candidate.field_description}" if candidate.field_description else ""}
{f"Context: {context}" if context else ""}

Picklist Values (in field order):
{picklist_list}

Based on industry knowledge and the picklist order, produce a complete process config with:
1. The correct sequential ordering of stages
2. Which stages are "parallel" (support stages running alongside main flow, not in the main sequence)
3. Which stages are "post_close" (lifecycle stages after the main workflow completes)
4. The predecessor/successor graph (stage_key references)
5. A brief description for each stage
6. A reasonable sla_target_days for each stage

Here is an example of the expected JSON format (truncated to 2 stages):
{_FEW_SHOT}

Respond with ONLY a JSON object in exactly this format. All stage_keys must be lowercase_snake_case.
```json
{{}}
```"""

    raw = _call_llm(prompt, model_id=model_id)
    data = _extract_json(raw)
    picklist_names = {pv.api_name for pv in candidate.picklist_values}
    return _validate_stage_structure(data, picklist_names)


def infer_entity_involvement(
    stage_structure: dict,
    related_objects: dict[str, SFObject],
    source_object: str,
    model_id: str = "us.anthropic.claude-sonnet-4-6",
) -> dict[str, list[dict]]:
    stages_desc = "\n".join(
        f"  - {s['name']} ({s['stage_key']}): {s.get('description', '')} [type: {s['stage_type']}]"
        for s in stage_structure.get("stages", [])
    )
    entity_summaries = "\n\n".join(
        _entity_summary(obj, related_objects)
        for obj in related_objects.values()
    )

    prompt = f"""You are mapping Salesforce entities to process stages. For each stage, identify which entities are involved, their role, and relevant fields.

Process: {stage_structure.get('name', '')}
Source Object: {source_object} (this should appear in most stages as "primary")

Stages:
{stages_desc}

Available Entities (with their fields and relationships):
{entity_summaries}

Rules:
- The source object ({source_object}) should appear in most stages as "primary"
- Entities with MasterDetail to source are likely "primary" in related stages
- Entities with Lookup to source are likely "reference" unless directly modified
- Include 2-6 entities per stage (most important ones)
- role must be "primary" or "reference"
- relevant_fields: 1-4 field api_names most relevant to that stage's purpose

Respond with ONLY a JSON object mapping stage_key to entity list:
```json
{{"stage_key": [{{"api_name": "...", "role": "primary", "relevant_fields": ["..."]}}]}}
```"""

    raw = _call_llm(prompt, model_id=model_id)
    data = _extract_json(raw)
    valid_objects = set(related_objects.keys())
    return _validate_entity_involvement(data, valid_objects)


def infer_synthetic_metrics(
    stage_structure: dict,
    context: str = "",
    initial_volume: int = 1000,
    model_id: str = "us.anthropic.claude-sonnet-4-6",
) -> dict[str, dict]:
    stage_list = "\n".join(
        f"  {s['order']}. {s['name']} ({s['stage_key']}) — type: {s['stage_type']}"
        for s in sorted(stage_structure.get("stages", []), key=lambda s: s["order"])
    )

    prompt = f"""You are generating realistic synthetic process metrics for a {context or 'financial services'} workflow.

Stages (in order):
{stage_list}

Generate realistic metrics for each stage. Constraints:
- entry_count starts at {initial_volume} for the first sequential stage
- entry_count must monotonically decrease through sequential stages (some drop-off at each stage)
- exit_count <= entry_count for every stage
- p50_days <= avg_days <= p90_days (always)
- sla_target_days should be realistic for the stage type
- bottleneck_severity must be one of: none, low, medium, high, critical
- Use "critical" for at most 1 stage, "high" for at most 2 stages
- error_rate and rework_rate between 0.0 and 0.25
- sla_met_pct between 0.5 and 1.0
- parallel (support) stages have lower entry_count (subset of records)
- post_close stages have avg_days=0 if they represent terminal states

Respond with ONLY a JSON object mapping stage_key to metrics:
```json
{{"stage_key": {{"avg_days": 1.2, "p50_days": 0.8, "p90_days": 2.5, "entry_count": 1000, "exit_count": 600, "error_rate": 0.03, "rework_rate": 0.02, "sla_target_days": 2.0, "sla_met_pct": 0.92, "bottleneck_severity": "none"}}}}
```"""

    raw = _call_llm(prompt, model_id=model_id)
    data = _extract_json(raw)

    seq_keys = [
        s["stage_key"]
        for s in sorted(stage_structure.get("stages", []), key=lambda s: s["order"])
        if s["stage_type"] == "sequential"
    ]
    return _validate_metrics(data, seq_keys)


def generate_process_config(
    candidate: ProcessCandidate,
    objects: dict[str, SFObject],
    context: str = "",
    model_id: str = "us.anthropic.claude-sonnet-4-6",
) -> dict:
    print(f"    Call 1/3: Inferring stage structure...")
    structure = infer_stage_structure(candidate, context=context, model_id=model_id)

    if not structure.get("domain") and candidate.domain:
        structure["domain"] = candidate.domain
    if not structure.get("source_object"):
        structure["source_object"] = candidate.source_object
    if not structure.get("stage_field"):
        structure["stage_field"] = candidate.stage_field
    structure["metrics_source"] = "synthetic"

    print(f"    Call 2/3: Mapping entity involvement...")
    related = _get_related_objects(candidate.source_object, objects)
    involvement = infer_entity_involvement(
        structure, related, candidate.source_object, model_id=model_id,
    )

    print(f"    Call 3/3: Generating synthetic metrics...")
    metrics = infer_synthetic_metrics(structure, context=context, model_id=model_id)

    for stage in structure.get("stages", []):
        key = stage["stage_key"]
        stage["involved_entities"] = involvement.get(key, [])
        stage["synthetic_metrics"] = metrics.get(key, {})
        if "sla_target_days" not in stage and metrics.get(key):
            stage["sla_target_days"] = metrics[key].get("sla_target_days", 0)

    return structure


def save_process_config(config: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    key = config.get("process_key", "unknown")
    path = output_dir / f"{key}.json"
    path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
