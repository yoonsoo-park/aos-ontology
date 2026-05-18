from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import shutil

from .config import DOMAIN_MAPPING, OBJECT_TIERS
from .models import SFField, SFObject, SFRelationship
from .vault_config import VaultConfig


def _yaml_dump_simple(data: dict) -> str:
    """Minimal YAML serializer for frontmatter — no external dependency."""
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f"{key}:")
            for item in value:
                first = True
                for k, v in item.items():
                    prefix = "  - " if first else "    "
                    lines.append(f"{prefix}{k}: {v}")
                    first = False
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                items = ", ".join(str(v) for v in value)
                lines.append(f"{key}: [{items}]")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        elif isinstance(value, str) and any(c in value for c in ":#{}[]|>&"):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _obj_label(api_name: str, objects: dict[str, SFObject]) -> str:
    obj = objects.get(api_name)
    if obj:
        return obj.clean_label
    name = api_name
    for ns in ("LLC_BI__", "nFORCE__", "nFORMS__", "nSBA__", "FinServ__"):
        name = name.removeprefix(ns)
    return name.removesuffix("__c").removesuffix("__mdt").replace("_", " ")


_TOP_FIELD_PATTERNS = ("Amount", "Stage", "Status", "Close Date", "Interest Rate", "Balance", "Term")
_HIGH_VALUE_PATTERNS = ("Date", "Rate", "Score", "Type", "Name", "Number")


def _key_fields(obj: SFObject, max_fields: int = 12) -> list[dict]:
    non_rel = [f for f in obj.fields if not f.is_relationship and f.label]

    def score(f: SFField) -> int:
        s = 0
        label_lower = f.label.lower()
        if any(p.lower() in label_lower for p in _TOP_FIELD_PATTERNS):
            s += 10
        elif any(p.lower() in label_lower for p in _HIGH_VALUE_PATTERNS):
            s += 3
        if f.type in ("Currency", "Percent"):
            s += 2
        if f.type in ("Picklist", "Date", "DateTime"):
            s += 1
        if f.required:
            s += 2
        if f.api_name.startswith(f"{obj.namespace}__") if obj.namespace else True:
            s += 1
        return s

    ranked = sorted(non_rel, key=score, reverse=True)

    selected: list[SFField] = []
    type_counts: dict[str, int] = {}
    max_per_type = max(3, max_fields // 4)
    for f in ranked:
        if len(selected) >= max_fields:
            break
        count = type_counts.get(f.type, 0)
        if count >= max_per_type:
            continue
        selected.append(f)
        type_counts[f.type] = count + 1

    return [
        {"name": f.api_name, "type": f.type, "label": f.label}
        for f in selected
    ]


def _format_relationship_line(rel: SFRelationship, objects: dict[str, SFObject], direction: str) -> str:
    if direction == "parent":
        target_label = _obj_label(rel.target_object, objects)
        desc = rel.description
        short_desc = f" — {desc[:80]}..." if len(desc) > 80 else (f" — {desc}" if desc else "")
        return f"- [[{target_label}]] via `{rel.field_api_name}` ({rel.relationship_type}){short_desc}"
    else:
        source_label = _obj_label(rel.source_object, objects)
        return f"- [[{source_label}]] via `{rel.field_api_name}` ({rel.relationship_type})"


def _format_picklist_section(fields: list[SFField]) -> str:
    picklist_fields = [f for f in fields if f.picklist_values]
    if not picklist_fields:
        return ""

    lines = ["\n## Key Picklists\n"]
    for f in picklist_fields[:5]:
        values = ", ".join(v.label or v.api_name for v in f.picklist_values[:10])
        suffix = f", ... (+{len(f.picklist_values) - 10} more)" if len(f.picklist_values) > 10 else ""
        lines.append(f"**{f.label}** (`{f.api_name}`): {values}{suffix}")
    return "\n".join(lines)


_TIER_LOOKUP: dict[str, int] = {}
for _tier, _objects in OBJECT_TIERS.items():
    for _obj_name in _objects:
        _TIER_LOOKUP[_obj_name] = _tier


def generate_entity_note(obj: SFObject, objects: dict[str, SFObject],
                         vault_config: VaultConfig | None = None) -> str:
    if vault_config:
        domain = vault_config.domain_mapping.get(obj.api_name, "uncategorized")
        tier = vault_config.tier_ranking.get(obj.api_name, 0)
    else:
        domain = DOMAIN_MAPPING.get(obj.api_name, "uncategorized")
        tier = _TIER_LOOKUP.get(obj.api_name, 0)
    key_fields = _key_fields(obj)

    frontmatter = {
        "api_name": obj.api_name,
        "label": obj.clean_label,
        "namespace": obj.namespace or "standard",
        "tier": tier,
        "domain": domain,
        "tags": [domain],
        "source_system": "salesforce",
        "source_provider": "salesforce-api",
        "freshness_sla": "realtime",
    }
    if obj.record_types:
        frontmatter["record_types"] = obj.record_types
    if key_fields:
        frontmatter["key_fields"] = key_fields
    frontmatter["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    fm_str = _yaml_dump_simple(frontmatter)

    sections: list[str] = []
    sections.append(f"---\n{fm_str}\n---\n")
    sections.append(f"# {obj.clean_label}\n")

    if obj.description:
        sections.append(f"{obj.description}\n")

    if obj.relationships or obj.incoming_relationships:
        sections.append("## Relationships\n")

        if obj.relationships:
            sections.append("### Parent (this object references)\n")
            for rel in obj.relationships:
                sections.append(_format_relationship_line(rel, objects, "parent"))
            sections.append("")

        if obj.incoming_relationships:
            sections.append("### Children (objects referencing this)\n")
            for rel in obj.incoming_relationships:
                sections.append(_format_relationship_line(rel, objects, "child"))
            sections.append("")

    picklist_section = _format_picklist_section(obj.fields)
    if picklist_section:
        sections.append(picklist_section)
        sections.append("")

    if key_fields:
        sections.append("## Key Fields\n")
        sections.append("| Field | Type | Label |")
        sections.append("|-------|------|-------|")
        for kf in key_fields:
            sections.append(f"| `{kf['name']}` | {kf['type']} | {kf['label']} |")
        sections.append("")

    sections.append(f"## Stats\n")
    sections.append(f"- **Total fields:** {len(obj.fields)}")
    sections.append(f"- **Relationships (outgoing):** {len(obj.relationships)}")
    sections.append(f"- **Relationships (incoming):** {len(obj.incoming_relationships)}")
    if obj.record_types:
        sections.append(f"- **Record types:** {', '.join(obj.record_types)}")

    return "\n".join(sections) + "\n"


def generate_domain_note(domain: str, objects: dict[str, SFObject],
                         vault_config: VaultConfig | None = None) -> str:
    dm = vault_config.domain_mapping if vault_config else DOMAIN_MAPPING
    domain_objects = [
        obj for obj in objects.values()
        if dm.get(obj.api_name) == domain
    ]
    if not domain_objects:
        return ""

    title = domain.replace("-", " ").title()
    lines = [f"# {title}\n"]
    lines.append("## Entities\n")
    for obj in sorted(domain_objects, key=lambda o: o.clean_label):
        desc = f" — {obj.description[:60]}..." if obj.description and len(obj.description) > 60 else (f" — {obj.description}" if obj.description else "")
        lines.append(f"- [[{obj.clean_label}]]{desc}")

    lines.append("")
    lines.append("## Entity Overview\n")
    lines.append("```dataview")
    lines.append("TABLE")
    lines.append('  relationships_out AS "Parents",')
    lines.append('  relationships_in AS "Children",')
    lines.append('  field_count AS "Fields",')
    lines.append('  namespace AS "Namespace"')
    lines.append('FROM "entities"')
    lines.append(f'WHERE domain = "{domain}"')
    lines.append("SORT relationships_in DESC")
    lines.append("```")

    return "\n".join(lines) + "\n"


def generate_index(objects: dict[str, SFObject],
                   vault_config: VaultConfig | None = None) -> str:
    dm = vault_config.domain_mapping if vault_config else DOMAIN_MAPPING
    index = {}
    for obj in objects.values():
        index[obj.api_name] = {
            "label": obj.clean_label,
            "file": f"entities/{obj.clean_label}.md",
            "domain": dm.get(obj.api_name, "uncategorized"),
            "relationships_out": len(obj.relationships),
            "relationships_in": len(obj.incoming_relationships),
            "field_count": len(obj.fields),
        }
    return json.dumps(index, indent=2, ensure_ascii=False)


def write_vault(objects: dict[str, SFObject], output_dir: Path,
                vault_config: VaultConfig | None = None) -> dict[str, int]:
    dm = vault_config.domain_mapping if vault_config else DOMAIN_MAPPING
    tr = vault_config.tier_ranking if vault_config else _TIER_LOOKUP

    entities_dir = output_dir / "entities"
    domains_dir = output_dir / "domains"
    meta_dir = output_dir / "_meta"

    for d in (entities_dir, domains_dir):
        if d.exists():
            shutil.rmtree(d)

    for d in (entities_dir, domains_dir, meta_dir):
        d.mkdir(parents=True, exist_ok=True)

    stats = {"entities": 0, "domains": 0}

    for obj in objects.values():
        note = generate_entity_note(obj, objects, vault_config)
        filepath = entities_dir / f"{obj.clean_label}.md"
        filepath.write_text(note, encoding="utf-8")
        stats["entities"] += 1

    seen_domains: set[str] = set()
    for api_name in objects:
        domain = dm.get(api_name)
        if domain and domain not in seen_domains:
            seen_domains.add(domain)
            note = generate_domain_note(domain, objects, vault_config)
            if note:
                filepath = domains_dir / f"{domain}.md"
                filepath.write_text(note, encoding="utf-8")
                stats["domains"] += 1

    index_content = generate_index(objects, vault_config)
    (meta_dir / "index.json").write_text(index_content, encoding="utf-8")

    config_source = vault_config.generated_by if vault_config else "hardcoded"
    max_tier = max((tr.get(api, 0) for api in objects), default=1)
    provenance = (
        f"# Source Provenance\n\n"
        f"- **Generated at:** {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"- **Source:** Demo-Master orgMetadata\n"
        f"- **Objects:** {len(objects)}\n"
        f"- **Scope:** Up to Tier {max_tier}\n"
        f"- **Config:** {config_source}\n"
        f"- **Completeness:** Standard nCino package schema only. No customer-specific customizations.\n"
    )
    (meta_dir / "source-provenance.md").write_text(provenance, encoding="utf-8")

    if vault_config:
        vault_config.save(meta_dir / "vault_config.json")

    return stats
