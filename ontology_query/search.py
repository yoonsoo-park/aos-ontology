from __future__ import annotations

import re
from dataclasses import dataclass, field

from .frontmatter import parse_frontmatter
from .index import OntologyIndex
from .reader import VaultReader


@dataclass
class RelationshipResult:
    entity: str
    field_api_name: str
    relationship_type: str
    description: str = ""


@dataclass
class EntityResult:
    api_name: str
    label: str
    domain: str
    namespace: str
    description: str
    source_system: str
    source_provider: str
    freshness_sla: str
    record_types: list[str]
    key_fields: list[dict]
    parents: list[RelationshipResult]
    children: list[RelationshipResult]
    field_count: int = 0


@dataclass
class EntitySummary:
    api_name: str
    label: str
    domain: str
    relationships_out: int
    relationships_in: int
    field_count: int


@dataclass
class FieldResult:
    entity: str
    entity_api_name: str
    field_name: str
    field_label: str
    field_type: str
    domain: str


@dataclass
class TraverseNode:
    entity: str
    api_name: str
    depth: int
    relationships: list[RelationshipResult] = field(default_factory=list)


_REL_PATTERN = re.compile(
    r"^- \[\[(.+?)\]\] via `(.+?)` \((\w+)\)(?: — (.*))?$"
)


class OntologySearch:
    def __init__(self, reader: VaultReader, index: OntologyIndex) -> None:
        self._reader = reader
        self._index = index
        self._cache: dict[str, tuple[dict, str]] = {}

    def _read_entity(self, name: str) -> tuple[dict, str] | None:
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

    def get_entity(self, name: str) -> EntityResult | None:
        parsed = self._read_entity(name)
        if not parsed:
            return None

        fm, body = parsed
        parents, children = self._parse_relationships(body)
        entry = self._index.get(name)

        return EntityResult(
            api_name=fm.get("api_name", ""),
            label=fm.get("label", ""),
            domain=fm.get("domain", ""),
            namespace=fm.get("namespace", ""),
            description=self._extract_description(body),
            source_system=fm.get("source_system", ""),
            source_provider=fm.get("source_provider", ""),
            freshness_sla=fm.get("freshness_sla", ""),
            record_types=fm.get("record_types", []),
            key_fields=fm.get("key_fields", []),
            parents=parents,
            children=children,
            field_count=entry.field_count if entry else 0,
        )

    def get_relationships(
        self, name: str, direction: str = "both", rel_type: str | None = None
    ) -> list[RelationshipResult]:
        parsed = self._read_entity(name)
        if not parsed:
            return []

        _, body = parsed
        parents, children = self._parse_relationships(body)

        if direction == "parent":
            rels = parents
        elif direction == "child":
            rels = children
        else:
            rels = parents + children

        if rel_type:
            rels = [r for r in rels if r.relationship_type.lower() == rel_type.lower()]
        return rels

    def list_domain(self, domain: str) -> list[EntitySummary]:
        return [
            EntitySummary(
                api_name=e.api_name,
                label=e.label,
                domain=e.domain,
                relationships_out=e.relationships_out,
                relationships_in=e.relationships_in,
                field_count=e.field_count,
            )
            for e in self._index.list_entities(domain)
        ]

    def traverse(self, start: str, depth: int = 2) -> list[TraverseNode]:
        visited: set[str] = set()
        result: list[TraverseNode] = []
        queue: list[tuple[str, int]] = [(start, 0)]

        while queue:
            name, d = queue.pop(0)
            name_lower = name.lower()
            if name_lower in visited or d > depth:
                continue
            visited.add(name_lower)

            rels = self.get_relationships(name)
            entry = self._index.get(name)
            api_name = entry.api_name if entry else name

            result.append(TraverseNode(
                entity=name,
                api_name=api_name,
                depth=d,
                relationships=rels,
            ))

            if d < depth:
                for rel in rels:
                    if rel.entity.lower() not in visited:
                        queue.append((rel.entity, d + 1))

        return result

    def search_fields(
        self,
        query: str,
        field_type: str | None = None,
        domain: str | None = None,
    ) -> list[FieldResult]:
        results: list[FieldResult] = []
        query_lower = query.lower()
        entities = self._index.list_entities(domain)

        for entry in entities:
            parsed = self._read_entity(entry.label)
            if not parsed:
                continue
            fm, _ = parsed
            for kf in fm.get("key_fields", []):
                name = kf.get("name", "")
                label = kf.get("label", "")
                ftype = kf.get("type", "")

                if field_type and ftype.lower() != field_type.lower():
                    continue
                if query_lower and query_lower not in name.lower() and query_lower not in label.lower():
                    continue

                results.append(FieldResult(
                    entity=entry.label,
                    entity_api_name=entry.api_name,
                    field_name=name,
                    field_label=label,
                    field_type=ftype,
                    domain=entry.domain,
                ))

        return results

    def _parse_relationships(
        self, body: str
    ) -> tuple[list[RelationshipResult], list[RelationshipResult]]:
        parents: list[RelationshipResult] = []
        children: list[RelationshipResult] = []
        current_section: list[RelationshipResult] | None = None

        for line in body.split("\n"):
            stripped = line.strip()
            if "Parent" in stripped and stripped.startswith("###"):
                current_section = parents
            elif "Children" in stripped and stripped.startswith("###"):
                current_section = children
            elif stripped.startswith("## ") and not stripped.startswith("### "):
                current_section = None
            elif current_section is not None:
                match = _REL_PATTERN.match(stripped)
                if match:
                    current_section.append(RelationshipResult(
                        entity=match.group(1),
                        field_api_name=match.group(2),
                        relationship_type=match.group(3),
                        description=match.group(4) or "",
                    ))

        return parents, children

    def _extract_description(self, body: str) -> str:
        lines = body.split("\n")
        desc_lines: list[str] = []
        past_title = False
        for line in lines:
            if line.startswith("# ") and not past_title:
                past_title = True
                continue
            if past_title:
                if line.startswith("## "):
                    break
                stripped = line.strip()
                if stripped:
                    desc_lines.append(stripped)
        return " ".join(desc_lines)
