from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class VaultConfig:
    domain_mapping: dict[str, str] = field(default_factory=dict)
    tier_ranking: dict[str, int] = field(default_factory=dict)
    generated_by: str = "manual"
    generated_at: str = ""
    context: str = ""

    def save(self, path: Path) -> None:
        data = asdict(self)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> VaultConfig:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            domain_mapping=data.get("domain_mapping", {}),
            tier_ranking=data.get("tier_ranking", {}),
            generated_by=data.get("generated_by", "unknown"),
            generated_at=data.get("generated_at", ""),
            context=data.get("context", ""),
        )

    @classmethod
    def from_hardcoded(cls) -> VaultConfig:
        from .config import DOMAIN_MAPPING, OBJECT_TIERS

        tier_ranking: dict[str, int] = {}
        for tier, objects in OBJECT_TIERS.items():
            for obj in objects:
                tier_ranking[obj] = tier

        return cls(
            domain_mapping=dict(DOMAIN_MAPPING),
            tier_ranking=tier_ranking,
            generated_by="hardcoded",
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
