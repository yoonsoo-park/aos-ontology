"""Entity enrichment pipeline — pluggable metadata augmentation for vault generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .models import SFObject
from .vault_config import VaultConfig


@dataclass
class Enrichment:
    key: str
    value: Any
    source: str  # "xml", "llm", "config", "derived"


@dataclass
class EnrichmentContext:
    all_objects: dict[str, SFObject]
    vault_config: VaultConfig | None = None
    options: dict[str, Any] = field(default_factory=dict)


class EntityEnricher(Protocol):
    name: str

    def enrich(self, obj: SFObject, context: EnrichmentContext) -> list[Enrichment]: ...


# --- Built-in Enrichers ---


class DescriptionEnricher:
    name = "description"

    def enrich(self, obj: SFObject, context: EnrichmentContext) -> list[Enrichment]:
        results: list[Enrichment] = []
        if obj.description:
            results.append(Enrichment("description", obj.description, "xml"))

        field_descriptions = []
        for f in obj.fields:
            if f.description and not f.is_relationship:
                field_descriptions.append({
                    "field": f.api_name,
                    "label": f.label,
                    "description": f.description,
                })
        if field_descriptions:
            results.append(Enrichment("field_descriptions", field_descriptions[:20], "xml"))

        return results


class ConstraintEnricher:
    name = "constraints"

    def enrich(self, obj: SFObject, context: EnrichmentContext) -> list[Enrichment]:
        constraints: list[dict[str, Any]] = []
        for f in obj.fields:
            if f.is_relationship:
                continue
            flags: list[str] = []
            if f.required:
                flags.append("required")
            if f.unique:
                flags.append("unique")
            if f.external_id:
                flags.append("external_id")
            if flags:
                constraints.append({
                    "field": f.api_name,
                    "label": f.label,
                    "flags": flags,
                })
        if not constraints:
            return []
        return [Enrichment("constraints", constraints, "xml")]


class PicklistSummaryEnricher:
    name = "picklists"

    def enrich(self, obj: SFObject, context: EnrichmentContext) -> list[Enrichment]:
        picklists: list[dict[str, Any]] = []
        for f in obj.fields:
            if f.picklist_values:
                picklists.append({
                    "field": f.api_name,
                    "label": f.label,
                    "value_count": len(f.picklist_values),
                    "values": [v.label or v.api_name for v in f.picklist_values[:15]],
                })
        if not picklists:
            return []
        return [Enrichment("picklist_fields", picklists, "xml")]


# --- Registry ---

ENRICHER_REGISTRY: dict[str, EntityEnricher] = {
    "description": DescriptionEnricher(),
    "constraints": ConstraintEnricher(),
    "picklists": PicklistSummaryEnricher(),
}


def get_enrichers(names: list[str]) -> list[EntityEnricher]:
    enrichers = []
    for name in names:
        enricher = ENRICHER_REGISTRY.get(name)
        if enricher is None:
            available = ", ".join(sorted(ENRICHER_REGISTRY.keys()))
            raise ValueError(f"Unknown enricher '{name}'. Available: {available}")
        enrichers.append(enricher)
    return enrichers


def run_enrichers(
    objects: dict[str, SFObject],
    enrichers: list[EntityEnricher],
    vault_config: VaultConfig | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Run all enrichers across all objects. Returns {api_name: {key: value}}."""
    ctx = EnrichmentContext(
        all_objects=objects,
        vault_config=vault_config,
        options=options or {},
    )
    result: dict[str, dict[str, Any]] = {}
    for obj in objects.values():
        entity_enrichments: dict[str, Any] = {}
        for enricher in enrichers:
            for e in enricher.enrich(obj, ctx):
                entity_enrichments[e.key] = e.value
        if entity_enrichments:
            result[obj.api_name] = entity_enrichments
    return result
