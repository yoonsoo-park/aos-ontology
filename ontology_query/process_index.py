"""Process index loader — reads _meta/process_index.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .reader import VaultReader


@dataclass
class ProcessIndexEntry:
    name: str
    label: str
    file: str
    domain: str
    stage_count: int
    cycle_time_days: float
    throughput: int
    bottleneck_severity: str
    bottleneck_stages: list[str]


class ProcessIndex:
    def __init__(self, reader: VaultReader) -> None:
        self._entries: dict[str, ProcessIndexEntry] = {}
        self._entity_map: dict[str, list[str]] = {}
        try:
            raw = json.loads(reader.read_file("_meta/process_index.json"))
        except (FileNotFoundError, OSError):
            return
        for key, data in raw.items():
            self._entries[key] = ProcessIndexEntry(
                name=key,
                label=data.get("label", key),
                file=data.get("file", ""),
                domain=data.get("domain", ""),
                stage_count=data.get("total_stages", 0),
                cycle_time_days=data.get("total_cycle_time_days", 0),
                throughput=data.get("throughput_per_month", 0),
                bottleneck_severity=data.get("top_bottleneck_severity", "none"),
                bottleneck_stages=data.get("bottleneck_stages", []),
            )
            for api_name, stages in data.get("entity_participation", {}).items():
                self._entity_map.setdefault(api_name, []).append(key)

    def get(self, name: str) -> ProcessIndexEntry | None:
        return self._entries.get(name)

    def list_all(self, domain: str | None = None) -> list[ProcessIndexEntry]:
        entries = list(self._entries.values())
        if domain:
            entries = [e for e in entries if e.domain == domain]
        return entries

    def get_processes_for_entity(self, api_name: str) -> list[str]:
        return self._entity_map.get(api_name, [])
