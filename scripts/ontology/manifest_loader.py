"""Manifest loader — port of aws-state-provisioning's ManifestProcessor for ontology use.

Reads a Manifest of Manifests (MoM) JSON file from a local Demo-Master clone,
recursively walks nested manifests, topologically sorts them by `dependencies`,
and extracts the set of Salesforce objectNames each manifest configures via
`configuration.sfRecordData.recordGroups.*.records[].objectName` and
`configuration.sfSeedData.recordGroups.*.records[].objectName`.

Compared to the TS ManifestProcessor, this is intentionally simpler:
  - No GitHub fetching (local clone only).
  - No commit SHA resolution / S3 raw cache.
  - No conditionTokens / provision evaluation — the ontology cares about which
    objects *can* appear in a setup, not which ones do for a given org.
  - No skipped-subtree tracking.

The loader is the foundation for replacing hardcoded TIER_1/TIER_2/DOMAIN_MAPPING
in `config.py` with derivations from the manifest DAG.

Usage:
    from scripts.ontology.manifest_loader import load_manifest_dag

    result = load_manifest_dag(
        repo_root="/path/to/Demo-Master",
        mom_path="stateProvisioning/manifest-of-manifests.json",
    )
    print(result.union_objects)              # set[str] — all objectNames seen
    for node in result.ordered_nodes:        # list[ManifestNode] — topo order
        print(node.alias, len(node.objects))
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

MAX_DEPTH = 10
"""Mirrors ManifestProcessor.MAX_DEPTH from aws-state-provisioning."""


@dataclass(frozen=True)
class ManifestNode:
    """A single manifest in the DAG, with the SF objects it configures."""

    alias: str
    """The manifest's alias (e.g. 'BASE', 'DATA'). Falls back to filename stem if missing."""

    path: str
    """Path to the manifest JSON, relative to the repo root."""

    depth: int
    """Tree depth from the root MoM (root = 0)."""

    parent_alias: str | None
    """Alias of the parent MoM that referenced this manifest, or None for the root."""

    dependencies: tuple[str, ...]
    """Aliases this manifest depends on at its level."""

    objects: frozenset[str]
    """SF API names referenced by this manifest's records (canonical case from manifest)."""

    is_mom: bool
    """True if this manifest references nested manifests (a Manifest of Manifests)."""


@dataclass
class ManifestLoadResult:
    """Result of loading a manifest DAG."""

    ordered_nodes: list[ManifestNode]
    """All nodes in topological order (dependencies first)."""

    union_objects: frozenset[str]
    """Union of all objectNames across all manifests, canonical case."""

    object_to_manifests: dict[str, frozenset[str]]
    """objectName (canonical) -> set of manifest aliases that reference it."""

    canonical_case: dict[str, str]
    """lowercase objectName -> canonical case (first occurrence wins)."""


class ManifestCycleError(Exception):
    """Raised when a circular dependency is detected in a MoM's manifests list."""


class ManifestDepthError(Exception):
    """Raised when nested manifest depth exceeds MAX_DEPTH."""


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _topo_sort(entries: list[dict]) -> list[dict]:
    """DFS topological sort over a single MoM's `manifests` list.

    Mirrors ManifestProcessor.sortManifestEntries — visits each entry's
    `dependencies` (aliases at the same level) before the entry itself.
    Raises ManifestCycleError on circular dependencies.
    """
    # Backfill missing aliases from path stem so topo sort works on either form.
    for e in entries:
        if not e.get("alias"):
            e["alias"] = _alias_from_path(e["path"])
    by_alias = {e["alias"]: e for e in entries}
    sorted_: list[dict] = []
    visited: set[str] = set()
    exploring: set[str] = set()

    def visit(entry: dict) -> None:
        alias = entry["alias"]
        if alias in visited:
            return
        if alias in exploring:
            chain = " -> ".join([*exploring, alias])
            raise ManifestCycleError(f"Circular dependency detected: {chain}")
        exploring.add(alias)
        for dep in entry.get("dependencies") or []:
            dep_entry = by_alias.get(dep)
            if dep_entry is None:
                raise ValueError(f"Dependency not found: {dep}")
            visit(dep_entry)
        exploring.discard(alias)
        visited.add(alias)
        sorted_.append(entry)

    for entry in entries:
        visit(entry)
    return sorted_


def _extract_object_names(manifest: dict) -> set[str]:
    """Pull objectNames from sfRecordData and sfSeedData record groups.

    We deliberately ignore `metadata`, `users`, `documents`, `attachments`,
    `permissionSets`, etc. — the ontology cares about Salesforce objects that
    receive *records* (data), not deployment artifacts.
    """
    cfg = manifest.get("configuration") or {}
    objects: set[str] = set()
    for key in ("sfRecordData", "sfSeedData"):
        section = cfg.get(key) or {}
        if not isinstance(section, dict):
            continue
        groups = section.get("recordGroups") or {}
        if not isinstance(groups, dict):
            continue
        for group in groups.values():
            for record in (group or {}).get("records") or []:
                obj = record.get("objectName")
                if isinstance(obj, str) and obj.strip():
                    objects.add(obj.strip())
    return objects


def _alias_from_path(manifest_path: str) -> str:
    """Fallback alias when an entry doesn't declare one — use filename stem."""
    return Path(manifest_path).stem


def _load_json(repo_root: Path, manifest_path: str) -> dict:
    full = repo_root / manifest_path
    if not full.exists():
        raise FileNotFoundError(f"Manifest not found: {full}")
    with full.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_manifest_dag(
    repo_root: str | Path,
    mom_path: str = "stateProvisioning/manifest-of-manifests.json",
) -> ManifestLoadResult:
    """Walk the manifest tree starting at `mom_path` and return the full DAG.

    Args:
        repo_root: path to a Demo-Master clone (or any repo with the same layout).
        mom_path: relative path to the root MoM JSON inside `repo_root`.

    Returns:
        ManifestLoadResult with topologically-ordered nodes and aggregated objects.

    Raises:
        ManifestCycleError: circular `dependencies` within a single MoM level.
        ManifestDepthError: nested manifest depth exceeds MAX_DEPTH.
        FileNotFoundError: referenced manifest path doesn't exist on disk.
    """
    repo_root = Path(repo_root)
    nodes: list[ManifestNode] = []
    canonical: dict[str, str] = {}  # lowercase -> first-seen canonical
    object_to_manifests: dict[str, set[str]] = {}

    def normalize(obj: str) -> str:
        """Case-fold for matching, but return the canonical (first-seen) casing."""
        key = obj.lower()
        canon = canonical.setdefault(key, obj)
        return canon

    def walk(
        manifest_path: str,
        alias: str | None,
        parent_alias: str | None,
        depth: int,
    ) -> None:
        if depth > MAX_DEPTH:
            raise ManifestDepthError(
                f"Max manifest depth ({MAX_DEPTH}) exceeded at '{manifest_path}'"
            )

        manifest = _load_json(repo_root, manifest_path)
        resolved_alias = alias or _alias_from_path(manifest_path)
        nested = manifest.get("manifests")
        is_mom = isinstance(nested, list) and len(nested) > 0

        # Collect objects for this manifest (configuration block, if any).
        raw_objects = _extract_object_names(manifest)
        canonical_objects = frozenset(normalize(o) for o in raw_objects)
        for obj in canonical_objects:
            object_to_manifests.setdefault(obj, set()).add(resolved_alias)

        # Determine this node's `dependencies` from the *parent's* entry, but
        # we don't have access to that here — we rely on the parent loop having
        # passed alias-level info. Simplest: read from the manifest itself if
        # it self-declares; else empty. (TS implementation tracks deps at the
        # MoM entry level, not inside the manifest body.)
        # The DAG ordering at the parent level is preserved by walking children
        # in topo order below.

        nodes.append(
            ManifestNode(
                alias=resolved_alias,
                path=manifest_path,
                depth=depth,
                parent_alias=parent_alias,
                dependencies=tuple(),  # populated for entries (set in child walk)
                objects=canonical_objects,
                is_mom=is_mom,
            )
        )

        if is_mom:
            sorted_entries = _topo_sort(nested)
            for entry in sorted_entries:
                child_path = entry["path"]
                child_alias = entry.get("alias") or _alias_from_path(child_path)
                child_deps = tuple(entry.get("dependencies") or [])
                # Push a placeholder index so we can backfill deps after walk.
                idx_before = len(nodes)
                walk(child_path, child_alias, resolved_alias, depth + 1)
                # The first node added by `walk` is the entry itself —
                # patch its dependencies field.
                if len(nodes) > idx_before:
                    n = nodes[idx_before]
                    nodes[idx_before] = ManifestNode(
                        alias=n.alias,
                        path=n.path,
                        depth=n.depth,
                        parent_alias=n.parent_alias,
                        dependencies=child_deps,
                        objects=n.objects,
                        is_mom=n.is_mom,
                    )

    walk(mom_path, alias=None, parent_alias=None, depth=0)

    union_objects = frozenset(canonical.values())
    return ManifestLoadResult(
        ordered_nodes=nodes,
        union_objects=union_objects,
        object_to_manifests={k: frozenset(v) for k, v in object_to_manifests.items()},
        canonical_case=dict(canonical),
    )


def diff_against_tier(
    tier_objects: Iterable[str],
    result: ManifestLoadResult,
) -> dict[str, list[str]]:
    """Compare a TIER list (e.g. config.OBJECT_TIERS[1] + [2]) to manifest objects.

    Returns a dict with three buckets:
      - 'exact': TIER objects that match a manifest object case-sensitively
      - 'case_mismatch': TIER objects matching only case-insensitively
                         (formatted as 'TIER_NAME -> MANIFEST_NAME')
      - 'missing': TIER objects with no manifest entry at all

    Used to surface normalization bugs (e.g. LLC_BI__Application__C typo) and
    schema-only entities that aren't in the dm-amer setup.
    """
    canon_lower = {k: v for k, v in result.canonical_case.items()}
    union = result.union_objects
    exact, case_mismatch, missing = [], [], []
    for t in tier_objects:
        if t in union:
            exact.append(t)
        else:
            canon = canon_lower.get(t.lower())
            if canon is not None:
                case_mismatch.append(f"{t} -> {canon}")
            else:
                missing.append(t)
    return {"exact": exact, "case_mismatch": case_mismatch, "missing": missing}
