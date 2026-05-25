"""Validate auto-derived tiers against the current hardcoded OBJECT_TIERS.

Usage:
    python -m scripts.ontology.validate_tier_derive \\
        --demo-master /tmp/Demo-Master \\
        [--report /tmp/tier-derive-report.md]

Outputs:
    - recall vs hardcoded T1, T2, T1+T2
    - missing items (in hardcoded but not auto-derived)
    - extra items (auto-derived T1/T2 not in hardcoded)
    - optional markdown report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import OBJECT_TIERS
from .manifest_loader import load_manifest_dag
from .parse_sf_metadata import parse_all_objects
from .tier_deriver import apply_overrides, compute_recall, derive_tiers
from .tier_overrides import FORCE_EXCLUDE, FORCE_T1, FORCE_T2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--demo-master",
        required=True,
        type=Path,
        help="Path to ncino/Demo-Master clone (DM-AMER-UAT branch)",
    )
    ap.add_argument(
        "--metadata-subpath",
        default="orgMetadata/main/default/objects",
        help="Relative path to SF metadata objects dir within Demo-Master",
    )
    ap.add_argument("--report", type=Path, help="Write a markdown report to this path")
    ap.add_argument("--recall-floor", type=float, default=0.80)
    args = ap.parse_args()

    demo: Path = args.demo_master
    metadata_root = demo / args.metadata_subpath
    if not metadata_root.is_dir():
        print(f"ERROR: metadata dir not found: {metadata_root}", file=sys.stderr)
        return 2

    print(f"[1/3] Loading manifest DAG from {demo} ...")
    manifest_result = load_manifest_dag(demo)
    manifest_objects = set(manifest_result.object_to_manifests.keys())
    print(
        f"      {len(manifest_result.ordered_nodes)} nodes, "
        f"{len(manifest_objects)} unique objects"
    )

    print(f"[2/3] Parsing SF metadata from {metadata_root} ...")
    objects = parse_all_objects(metadata_root)
    print(f"      {len(objects)} objects parsed")

    print("[3/3] Deriving tiers ...")
    auto = derive_tiers(objects, manifest_objects)
    print(
        f"      [auto] filtered → {len(auto.scored)} candidates, "
        f"T1={len(auto.tier_1)}, T2={len(auto.tier_2)}"
    )
    result = apply_overrides(
        auto,
        force_t1=FORCE_T1,
        force_t2=FORCE_T2,
        force_exclude=FORCE_EXCLUDE,
    )
    print(
        f"      [final] T1={len(result.tier_1)}, T2={len(result.tier_2)}, "
        f"T3={len(result.tier_3)}  (FORCE_T1={len(FORCE_T1)}, "
        f"FORCE_T2={len(FORCE_T2)}, EXCLUDE={len(FORCE_EXCLUDE)})"
    )

    baseline_t1 = OBJECT_TIERS.get(1, [])
    baseline_t2 = OBJECT_TIERS.get(2, [])
    baseline_all = baseline_t1 + baseline_t2

    r1, _, miss_t1 = compute_recall(result.tier_1, baseline_t1)
    r2, _, miss_t2 = compute_recall(result.tier_2, baseline_t2)
    r_all, _, miss_all = compute_recall(result.all_tiered, baseline_all)

    derived_all_ci = {n.lower() for n in result.all_tiered}
    baseline_all_ci = {n.lower() for n in baseline_all}
    extra = sorted(n for n in result.all_tiered if n.lower() not in baseline_all_ci)

    print("\n=== RESULTS ===")
    print(f"  T1 recall      : {r1:.1%}  ({len(baseline_t1) - len(miss_t1)}/{len(baseline_t1)})")
    print(f"  T2 recall      : {r2:.1%}  ({len(baseline_t2) - len(miss_t2)}/{len(baseline_t2)})")
    print(f"  T1+T2 recall   : {r_all:.1%}  ({len(baseline_all) - len(miss_all)}/{len(baseline_all)})")
    print(f"  extras (not in baseline T1+T2): {len(extra)}")

    pass_floor = r_all >= args.recall_floor
    print(f"\n  recall floor   : {args.recall_floor:.0%}  →  {'PASS' if pass_floor else 'FAIL'}")

    if args.report:
        _write_report(
            args.report,
            result=result,
            baseline_t1=baseline_t1,
            baseline_t2=baseline_t2,
            r1=r1,
            r2=r2,
            r_all=r_all,
            miss_t1=miss_t1,
            miss_t2=miss_t2,
            miss_all=miss_all,
            extra=extra,
            manifest_count=len(manifest_objects),
            metadata_count=len(objects),
        )
        print(f"\n  report → {args.report}")

    return 0 if pass_floor else 1


def _write_report(path: Path, **kw) -> None:
    result = kw["result"]
    lines: list[str] = []
    lines.append("# Tier Auto-Derive Validation Report\n")
    lines.append(f"- manifest objects: {kw['manifest_count']}")
    lines.append(f"- metadata objects parsed: {kw['metadata_count']}")
    lines.append(f"- candidates after Pass 1: {len(result.scored)}")
    lines.append(f"- T1 size: {len(result.tier_1)}, T2 size: {len(result.tier_2)}, T3 size: {len(result.tier_3)}\n")

    lines.append("## Recall vs hardcoded\n")
    lines.append(f"| metric | value |")
    lines.append(f"|---|---|")
    lines.append(f"| T1 recall | {kw['r1']:.1%} |")
    lines.append(f"| T2 recall | {kw['r2']:.1%} |")
    lines.append(f"| T1+T2 recall | {kw['r_all']:.1%} |\n")

    lines.append(f"## Missing from auto-derived (in baseline T1, not in derived T1) — {len(kw['miss_t1'])}\n")
    for n in kw["miss_t1"]:
        lines.append(f"- {n}")
    lines.append("")

    lines.append(f"## Missing from auto-derived T2 — {len(kw['miss_t2'])}\n")
    for n in kw["miss_t2"]:
        lines.append(f"- {n}")
    lines.append("")

    lines.append(f"## Missing from T1+T2 combined — {len(kw['miss_all'])}\n")
    for n in kw["miss_all"]:
        lines.append(f"- {n}")
    lines.append("")

    lines.append(f"## Extras (auto-derived but not in baseline) — {len(kw['extra'])}\n")
    for n in kw["extra"]:
        lines.append(f"- {n}")
    lines.append("")

    lines.append("## Top 30 derived T1 with scores\n")
    lines.append("| rank | api_name | namespace | in | out | rt | manifest | score |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, s in enumerate(result.scored[:30], 1):
        lines.append(
            f"| {i} | {s.api_name} | {s.namespace or 'std'} | {s.in_degree} | "
            f"{s.out_degree} | {'✓' if s.has_record_types else ''} | "
            f"{'✓' if s.in_manifest else ''} | {s.score:.1f} |"
        )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
