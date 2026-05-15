from __future__ import annotations

from dataclasses import dataclass

from .search import OntologySearch


@dataclass
class SourceMapping:
    entity: str
    api_name: str
    provider: str
    freshness_sla: str
    source_system: str


class SourceResolver:
    def __init__(self, search: OntologySearch) -> None:
        self._search = search

    def resolve(self, entity_name: str) -> SourceMapping | None:
        entity = self._search.get_entity(entity_name)
        if not entity:
            return None

        return SourceMapping(
            entity=entity.label,
            api_name=entity.api_name,
            provider=entity.source_provider,
            freshness_sla=entity.freshness_sla,
            source_system=entity.source_system,
        )

    def resolve_chain(self, entity_name: str, depth: int = 2) -> list[SourceMapping]:
        nodes = self._search.traverse(entity_name, depth=depth)
        mappings: list[SourceMapping] = []
        seen: set[str] = set()

        for node in nodes:
            if node.api_name in seen:
                continue
            seen.add(node.api_name)
            mapping = self.resolve(node.entity)
            if mapping:
                mappings.append(mapping)

        return mappings
