from __future__ import annotations

import json
from dataclasses import dataclass

from .reader import VaultReader


@dataclass
class EntityEntry:
    api_name: str
    label: str
    file: str
    domain: str
    relationships_out: int
    relationships_in: int
    field_count: int


class OntologyIndex:
    def __init__(self, reader: VaultReader) -> None:
        raw = json.loads(reader.read_file("_meta/index.json"))
        self._by_api_name: dict[str, EntityEntry] = {}
        self._by_label: dict[str, EntityEntry] = {}

        for api_name, data in raw.items():
            entry = EntityEntry(
                api_name=api_name,
                label=data["label"],
                file=data["file"],
                domain=data["domain"],
                relationships_out=data.get("relationships_out", 0),
                relationships_in=data.get("relationships_in", 0),
                field_count=data.get("field_count", 0),
            )
            self._by_api_name[api_name] = entry
            self._by_label[data["label"].lower()] = entry

    def get(self, name: str) -> EntityEntry | None:
        entry = self._by_api_name.get(name)
        if entry:
            return entry
        return self._by_label.get(name.lower())

    def list_entities(self, domain: str | None = None) -> list[EntityEntry]:
        entries = list(self._by_api_name.values())
        if domain:
            entries = [e for e in entries if e.domain == domain]
        return sorted(entries, key=lambda e: e.label)

    def list_domains(self) -> list[str]:
        return sorted({e.domain for e in self._by_api_name.values()})

    @property
    def size(self) -> int:
        return len(self._by_api_name)
