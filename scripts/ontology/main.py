#!/usr/bin/env python3
"""Generate an Obsidian vault from Salesforce XML metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import DEFAULT_METADATA_ROOT, OBJECT_TIERS, TIER_1_OBJECTS, get_objects_for_tier
from .generate_vault import write_vault
from .parse_sf_metadata import parse_all_objects


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Obsidian ontology vault from Salesforce metadata XML")
    parser.add_argument(
        "--metadata-root",
        type=Path,
        default=DEFAULT_METADATA_ROOT,
        help="Path to orgMetadata/main/default/objects/",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/vault"),
        help="Output directory for generated vault",
    )
    parser.add_argument(
        "--all-objects",
        action="store_true",
        help="Parse all objects instead of Tier 1 only",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default=None,
        help="Filter by namespace (e.g., LLC_BI)",
    )
    parser.add_argument(
        "--tier",
        type=int,
        default=None,
        help="Generate up to this tier (1, 2, ...). Default: max tier.",
    )
    args = parser.parse_args()

    if not args.metadata_root.exists():
        print(f"Error: metadata root not found: {args.metadata_root}", file=sys.stderr)
        sys.exit(1)

    if args.all_objects:
        object_filter = None
        if args.namespace:
            all_dirs = [d.name for d in args.metadata_root.iterdir() if d.is_dir()]
            object_filter = [name for name in all_dirs if name.startswith(f"{args.namespace}__")]
    elif args.tier is not None:
        object_filter = get_objects_for_tier(args.tier)
    else:
        max_tier = max(OBJECT_TIERS.keys())
        object_filter = get_objects_for_tier(max_tier)

    print(f"Parsing metadata from: {args.metadata_root}")
    print(f"Object filter: {'all' if object_filter is None else f'{len(object_filter)} objects'}")

    objects = parse_all_objects(args.metadata_root, object_filter)
    print(f"Parsed {len(objects)} objects")

    total_fields = sum(len(o.fields) for o in objects.values())
    total_rels = sum(len(o.relationships) for o in objects.values())
    print(f"Total fields: {total_fields}, Total relationships: {total_rels}")

    stats = write_vault(objects, args.output)
    print(f"\nVault generated at: {args.output}")
    print(f"  Entities: {stats['entities']}")
    print(f"  Domains: {stats['domains']}")


if __name__ == "__main__":
    main()
