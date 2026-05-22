#!/usr/bin/env python3
"""Generate an Obsidian vault from Salesforce XML metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import DEFAULT_METADATA_ROOT, DOMAIN_MAPPING, OBJECT_TIERS, TIER_1_OBJECTS, get_objects_for_tier
from .generate_vault import write_vault
from .parse_sf_metadata import parse_all_objects
from .vault_config import VaultConfig


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
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Use LLM agent to auto-classify domains and tiers",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Use pre-generated vault_config.json (skip agent)",
    )
    parser.add_argument(
        "--context",
        type=str,
        default="",
        help="Context hint for agent (e.g., 'banking/lending SaaS')",
    )
    parser.add_argument(
        "--save-config",
        type=Path,
        default=None,
        help="Save generated config to JSON for review/reuse",
    )
    parser.add_argument(
        "--processes",
        action="store_true",
        help="Generate process bottleneck analysis notes",
    )
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Generate unified graph.json + metrics overlay",
    )
    parser.add_argument(
        "--discover-processes",
        action="store_true",
        help="Use LLM agent to auto-generate process configs from SF metadata",
    )
    parser.add_argument(
        "--process-source",
        type=str,
        default=None,
        help="Target specific source object for process discovery (e.g., LLC_BI__Loan__c)",
    )
    parser.add_argument(
        "--save-process-config",
        type=Path,
        default=None,
        help="Save generated process config(s) to directory for review",
    )
    parser.add_argument(
        "--enrich",
        type=str,
        default=None,
        help="Comma-separated enricher names (e.g., description,constraints,picklists)",
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

    vault_config: VaultConfig | None = None
    if args.config:
        print(f"Loading config from: {args.config}")
        vault_config = VaultConfig.load(args.config)
    elif args.agent:
        from .agent_assist import generate_vault_config

        print("Running agent-assisted config generation...")
        vault_config = generate_vault_config(
            objects,
            context=args.context,
            existing_domains=None,
        )
        print(f"  Agent assigned {len(set(vault_config.domain_mapping.values()))} domains")

    if args.save_config and vault_config:
        vault_config.save(args.save_config)
        print(f"Config saved to: {args.save_config}")

    enrichment_map = None
    if args.enrich:
        from .enrichers import get_enrichers, run_enrichers

        enricher_names = [n.strip() for n in args.enrich.split(",")]
        enrichers = get_enrichers(enricher_names)
        print(f"\nRunning enrichers: {', '.join(enricher_names)}")
        enrichment_map = run_enrichers(objects, enrichers, vault_config)
        enriched_count = len(enrichment_map)
        print(f"  Enriched {enriched_count} entities")

    stats = write_vault(objects, args.output, vault_config, enrichment_map)
    print(f"\nVault generated at: {args.output}")
    print(f"  Entities: {stats['entities']}")
    print(f"  Domains: {stats['domains']}")

    from .generate_obsidian_config import write_obsidian_config
    dm = vault_config.domain_mapping if vault_config else DOMAIN_MAPPING
    all_domains = sorted({d for d in dm.values() if d != "uncategorized"})
    write_obsidian_config(args.output, all_domains)
    print(f"  Obsidian config: .obsidian/ (graph colors, snippets, plugins)")

    if args.discover_processes:
        from .process_agent import (
            discover_process_candidates,
            generate_process_config,
            save_process_config,
        )

        dm = vault_config.domain_mapping if vault_config else DOMAIN_MAPPING
        print("\nDiscovering process candidates from metadata...")
        candidates = discover_process_candidates(objects, domain_mapping=dm)
        if args.process_source:
            candidates = [c for c in candidates if c.source_object == args.process_source]

        print(f"  Found {len(candidates)} process candidate(s)")
        for cand in candidates:
            print(f"    - {cand.source_object}.{cand.stage_field} ({len(cand.picklist_values)} stages)")

        configs_dir = args.save_process_config or (Path(__file__).parent.parent.parent / "configs" / "processes")
        for cand in candidates:
            print(f"\n  Generating config for {cand.source_object}...")
            config = generate_process_config(cand, objects, context=args.context)
            path = save_process_config(config, configs_dir)
            print(f"  Saved: {path}")

    if args.processes:
        from .generate_processes import write_processes

        print("\nGenerating process bottleneck analysis...")
        proc_stats = write_processes(args.output)
        print(f"  Processes: {proc_stats['processes']}")
        print(f"  Stages: {proc_stats['stages']}")

    if args.graph:
        from .generate_graph import write_graph
        from .graph_builder import build_graph
        from .metrics import SyntheticMetricsAdapter
        from .process_config_loader import load_all_process_configs

        print("\nGenerating unified graph...")
        process_configs = load_all_process_configs()
        graph = build_graph(objects, process_configs, vault_config)
        adapter = SyntheticMetricsAdapter(process_configs)
        graph_stats = write_graph(
            graph, args.output,
            metrics_adapter=adapter,
            process_keys=list(process_configs.keys()),
        )
        print(f"  Nodes: {graph_stats['nodes']}")
        print(f"  Edges: {graph_stats['edges']}")
        print(f"  Metrics files: {graph_stats['metrics_files']}")


if __name__ == "__main__":
    main()
