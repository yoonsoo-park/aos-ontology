"""Agent-assisted ontology config generation using Bedrock Claude."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from .models import SFObject
from .vault_config import VaultConfig


def _call_llm(prompt: str, model_id: str = "us.anthropic.claude-sonnet-4-6", region: str = "us-east-1") -> str:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def _extract_json(text: str) -> dict | list:
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    raw = match.group(1) if match else text
    return json.loads(raw)


def _entity_summary(obj: SFObject, objects: dict[str, SFObject]) -> str:
    top_fields = []
    for f in obj.fields[:8]:
        if not f.is_relationship and f.label:
            top_fields.append(f"{f.label} ({f.type})")
    rel_targets = [r.target_object for r in obj.relationships[:5]]
    incoming = [r.source_object for r in obj.incoming_relationships[:5]]

    parts = [f"- {obj.api_name} ({obj.clean_label})"]
    if obj.description:
        parts.append(f"  desc: {obj.description[:120]}")
    if top_fields:
        parts.append(f"  fields: {', '.join(top_fields[:6])}")
    if rel_targets:
        parts.append(f"  references: {', '.join(rel_targets)}")
    if incoming:
        parts.append(f"  referenced_by: {', '.join(incoming)}")
    return "\n".join(parts)


def _batch_entities(objects: dict[str, SFObject], batch_size: int = 50) -> list[list[str]]:
    keys = list(objects.keys())
    return [keys[i:i + batch_size] for i in range(0, len(keys), batch_size)]


def infer_domain_mapping(
    objects: dict[str, SFObject],
    existing_domains: list[str] | None = None,
    context: str = "",
    model_id: str = "us.anthropic.claude-sonnet-4-6",
) -> dict[str, str]:
    result: dict[str, str] = {}
    batches = _batch_entities(objects)

    domain_hint = ""
    if existing_domains:
        domain_hint = f"\nPrefer reusing these existing domain slugs when appropriate: {', '.join(existing_domains)}\n"

    for batch_keys in batches:
        summaries = "\n\n".join(_entity_summary(objects[k], objects) for k in batch_keys)

        prompt = f"""You are an expert data architect. Classify each entity below into a semantic domain.

{f"Context: {context}" if context else ""}
{domain_hint}
Rules:
- Domain slugs must be lowercase-kebab-case (e.g., "loan-origination", "treasury-management")
- Group related entities into the same domain
- Use 8-20 domains total (not too granular, not too broad)
- Every entity must be assigned exactly one domain

Entities:
{summaries}

Respond with ONLY a JSON object mapping api_name to domain slug:
```json
{{"api_name": "domain-slug", ...}}
```"""

        try:
            raw = _call_llm(prompt, model_id=model_id)
            batch_result = _extract_json(raw)
            if isinstance(batch_result, dict):
                result.update(batch_result)
        except Exception as e:
            print(f"  Warning: agent domain classification failed for batch: {e}")
            for k in batch_keys:
                result.setdefault(k, "uncategorized")

    return result


def infer_tier_ranking(
    objects: dict[str, SFObject],
    max_tiers: int = 3,
    model_id: str = "us.anthropic.claude-sonnet-4-6",
) -> dict[str, int]:
    in_degree: dict[str, int] = {k: 0 for k in objects}
    for obj in objects.values():
        for rel in obj.relationships:
            if rel.target_object in in_degree:
                in_degree[rel.target_object] += 1

    sorted_entities = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)
    entity_list = "\n".join(
        f"- {api} (label: {objects[api].clean_label}, in-degree: {deg}, "
        f"fields: {len(objects[api].fields)}, "
        f"out-rels: {len(objects[api].relationships)})"
        for api, deg in sorted_entities
    )

    prompt = f"""You are an expert data architect. Rank these entities into {max_tiers} tiers based on their business importance and centrality.

Tier 1 = core business entities (most important, heavily referenced)
Tier 2 = extended/supporting entities
Tier 3 = peripheral/specialized entities

I've pre-computed the in-degree (how many other entities reference each one) as a signal.
Use this plus your understanding of the entity names and field counts to assign tiers.

Entities (sorted by in-degree descending):
{entity_list}

Respond with ONLY a JSON object mapping api_name to tier number (1, 2, or 3):
```json
{{"api_name": 1, ...}}
```"""

    try:
        raw = _call_llm(prompt, model_id=model_id)
        result = _extract_json(raw)
        if isinstance(result, dict):
            return {k: int(v) for k, v in result.items()}
    except Exception as e:
        print(f"  Warning: agent tier ranking failed: {e}")

    total = len(sorted_entities)
    t1 = max(1, total // 5)
    t2 = max(1, total // 3)
    fallback: dict[str, int] = {}
    for i, (api, _) in enumerate(sorted_entities):
        if i < t1:
            fallback[api] = 1
        elif i < t1 + t2:
            fallback[api] = 2
        else:
            fallback[api] = 3
    return fallback


def generate_vault_config(
    objects: dict[str, SFObject],
    context: str = "",
    existing_domains: list[str] | None = None,
    max_tiers: int = 3,
    model_id: str = "us.anthropic.claude-sonnet-4-6",
) -> VaultConfig:
    print(f"  Agent: classifying {len(objects)} entities into domains...")
    domain_mapping = infer_domain_mapping(
        objects,
        existing_domains=existing_domains,
        context=context,
        model_id=model_id,
    )

    print(f"  Agent: ranking {len(objects)} entities into {max_tiers} tiers...")
    tier_ranking = infer_tier_ranking(
        objects,
        max_tiers=max_tiers,
        model_id=model_id,
    )

    return VaultConfig(
        domain_mapping=domain_mapping,
        tier_ranking=tier_ranking,
        generated_by="agent",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        context=context,
    )
