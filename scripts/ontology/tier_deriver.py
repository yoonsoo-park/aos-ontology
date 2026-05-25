"""Auto-derive OBJECT_TIERS from manifest DAG + parsed SF metadata.

Replaces hardcoded TIER_1/TIER_2 in config.py with a deterministic algorithm:

Pass 1 (filter):
    - exclude INFRA_EXCLUDE (User, Profile, RecordType, Organization)
    - include if namespace == LLC_BI
    - include if namespace == nSBA
    - include if namespace == "" (standard) AND in_manifest AND in_degree >= 5
    - exclude everything else (notably nFORCE — 0/69 in current TIERs)

Pass 2 (score & rank):
    score = in_degree * 2
          + (10 if has_record_types else 0)
          + (30 if in_manifest else 0)
          + out_degree * 0.5
    Top 28 → TIER_1, next 80 → TIER_2, rest → TIER_3 (T1=28, T2=80 fixed).

See issue #2: https://github.com/yoonsoo-park/aos-ontology/issues/2
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import SFObject

INFRA_EXCLUDE: frozenset[str] = frozenset(
    {"User", "Profile", "RecordType", "Organization"}
)

TIER_1_SIZE = 28
TIER_2_SIZE = 81  # matches current baseline (config.OBJECT_TIERS[2])

# Pass 1 inclusion thresholds
STD_IN_DEGREE_MIN = 5

# Pass 2 score weights
W_IN_DEGREE = 2.0
W_HAS_RECORD_TYPES = 10.0
W_IN_MANIFEST = 30.0
W_OUT_DEGREE = 0.5


@dataclass(frozen=True)
class ScoredObject:
    api_name: str
    namespace: str
    in_degree: int
    out_degree: int
    has_record_types: bool
    in_manifest: bool
    score: float


@dataclass(frozen=True)
class TierAssignment:
    tier_1: list[str]
    tier_2: list[str]
    tier_3: list[str]
    scored: list[ScoredObject]  # sorted desc by score, included objects only

    @property
    def all_tiered(self) -> list[str]:
        return self.tier_1 + self.tier_2


def _passes_filter(
    api_name: str, namespace: str, in_manifest: bool, in_degree: int
) -> bool:
    if api_name in INFRA_EXCLUDE:
        return False
    if namespace == "LLC_BI":
        return True
    if namespace == "nSBA":
        return True
    if namespace == "" and in_manifest and in_degree >= STD_IN_DEGREE_MIN:
        return True
    return False


def _score(
    in_degree: int, out_degree: int, has_record_types: bool, in_manifest: bool
) -> float:
    s = W_IN_DEGREE * in_degree + W_OUT_DEGREE * out_degree
    if has_record_types:
        s += W_HAS_RECORD_TYPES
    if in_manifest:
        s += W_IN_MANIFEST
    return s


def derive_tiers(
    objects: dict[str, SFObject],
    manifest_objects: set[str],
    *,
    tier_1_size: int = TIER_1_SIZE,
    tier_2_size: int = TIER_2_SIZE,
) -> TierAssignment:
    """Return TierAssignment derived from parsed objects + manifest object set.

    Args:
        objects: api_name -> SFObject (from parse_all_objects)
        manifest_objects: canonical api_names referenced by dm-amer manifest DAG
                          (from manifest_loader.collect_objects, normalized)
    """
    scored: list[ScoredObject] = []
    # Build a case-insensitive manifest lookup since manifest_loader returns
    # canonical-first-wins names which may not exactly match metadata casing.
    manifest_ci = {n.lower() for n in manifest_objects}

    for api_name, obj in objects.items():
        in_deg = len(obj.incoming_relationships)
        out_deg = len(obj.relationships)
        in_manifest = api_name.lower() in manifest_ci
        if not _passes_filter(api_name, obj.namespace, in_manifest, in_deg):
            continue
        scored.append(
            ScoredObject(
                api_name=api_name,
                namespace=obj.namespace,
                in_degree=in_deg,
                out_degree=out_deg,
                has_record_types=bool(obj.record_types),
                in_manifest=in_manifest,
                score=_score(in_deg, out_deg, bool(obj.record_types), in_manifest),
            )
        )

    # Stable sort: score desc, then api_name asc for determinism
    scored.sort(key=lambda s: (-s.score, s.api_name))

    api_names = [s.api_name for s in scored]
    tier_1 = api_names[:tier_1_size]
    tier_2 = api_names[tier_1_size : tier_1_size + tier_2_size]
    tier_3 = api_names[tier_1_size + tier_2_size :]

    return TierAssignment(tier_1=tier_1, tier_2=tier_2, tier_3=tier_3, scored=scored)


def apply_overrides(
    assignment: TierAssignment,
    *,
    force_t1: list[str] | None = None,
    force_t2: list[str] | None = None,
    force_exclude: list[str] | None = None,
    tier_1_size: int = TIER_1_SIZE,
    tier_2_size: int = TIER_2_SIZE,
) -> TierAssignment:
    """Layer manual overrides on top of an auto-derived TierAssignment.

    Semantics:
        - FORCE_T1 entries are guaranteed to land in tier_1.
        - FORCE_T2 entries are guaranteed to land in tier_2 (unless also in FORCE_T1).
        - FORCE_EXCLUDE entries are removed from all tiers.
        - To make room, existing auto-derived entries are pushed down
          (T1 overflow → T2, T2 overflow → T3) preserving score order.
        - Sizes (T1/T2) stay fixed — combined size may grow if FORCE_T1+FORCE_T2
          exceed tier_1_size+tier_2_size, in which case T1/T2 are exactly
          their force lists plus highest-scored auto entries up to size.

    Returns a new TierAssignment. `scored` is preserved unchanged (auto signals).
    """
    force_t1 = list(force_t1 or [])
    force_t2 = list(force_t2 or [])
    exclude_ci = {e.lower() for e in (force_exclude or [])}

    # Dedup: if same name in both force lists, T1 wins
    force_t1_ci = {n.lower() for n in force_t1}
    force_t2 = [n for n in force_t2 if n.lower() not in force_t1_ci]

    forced_all_ci = force_t1_ci | {n.lower() for n in force_t2}

    # Auto-derived order, minus anything force-listed or excluded
    auto_order = [
        s.api_name
        for s in assignment.scored
        if s.api_name.lower() not in forced_all_ci
        and s.api_name.lower() not in exclude_ci
    ]

    # T1 = forced T1 + auto fill
    t1 = list(force_t1)
    t1_remaining = max(0, tier_1_size - len(t1))
    t1.extend(auto_order[:t1_remaining])
    used_from_auto = t1_remaining

    # T2 = forced T2 + auto fill
    t2 = list(force_t2)
    t2_remaining = max(0, tier_2_size - len(t2))
    t2.extend(auto_order[used_from_auto : used_from_auto + t2_remaining])
    used_from_auto += t2_remaining

    # T3 = leftover auto entries
    t3 = auto_order[used_from_auto:]

    return TierAssignment(tier_1=t1, tier_2=t2, tier_3=t3, scored=assignment.scored)


def compute_recall(
    derived: list[str], baseline: list[str]
) -> tuple[float, list[str], list[str]]:
    """Recall vs hardcoded baseline.

    Returns: (recall, hits, misses). Case-insensitive comparison.
    """
    derived_ci = {d.lower() for d in derived}
    hits = [b for b in baseline if b.lower() in derived_ci]
    misses = [b for b in baseline if b.lower() not in derived_ci]
    recall = len(hits) / len(baseline) if baseline else 0.0
    return recall, hits, misses
