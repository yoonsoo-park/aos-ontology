#!/usr/bin/env python3
"""Ontology query CLI demo — test all query patterns locally without deployment."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from ontology_query.reader import LocalVaultReader
from ontology_query.index import OntologyIndex
from ontology_query.search import OntologySearch
from ontology_query.resolver import SourceResolver
from ontology_query.process_search import ProcessSearch


def _json(obj) -> str:
    if hasattr(obj, "__dataclass_fields__"):
        return json.dumps(asdict(obj), indent=2, ensure_ascii=False)
    if isinstance(obj, list):
        return json.dumps([asdict(o) for o in obj], indent=2, ensure_ascii=False)
    return json.dumps(obj, indent=2, ensure_ascii=False)


def cmd_entity(search: OntologySearch, name: str) -> None:
    entity = search.get_entity(name)
    if not entity:
        print(f"Entity not found: {name}", file=sys.stderr)
        sys.exit(1)
    print(_json(entity))


def cmd_domain(search: OntologySearch, domain: str) -> None:
    entities = search.list_domain(domain)
    if not entities:
        print(f"No entities in domain: {domain}", file=sys.stderr)
        sys.exit(1)
    print(_json(entities))


def cmd_traverse(search: OntologySearch, name: str, depth: int) -> None:
    nodes = search.traverse(name, depth=depth)
    if not nodes:
        print(f"Entity not found: {name}", file=sys.stderr)
        sys.exit(1)
    print(_json(nodes))


def cmd_resolve(resolver: SourceResolver, name: str) -> None:
    mapping = resolver.resolve(name)
    if not mapping:
        print(f"Entity not found: {name}", file=sys.stderr)
        sys.exit(1)
    print(_json(mapping))


def cmd_resolve_chain(resolver: SourceResolver, name: str, depth: int) -> None:
    chain = resolver.resolve_chain(name, depth=depth)
    print(_json(chain))


def cmd_domains(index: OntologyIndex) -> None:
    for d in index.list_domains():
        count = len(index.list_entities(domain=d))
        print(f"  {d} ({count} entities)")


def cmd_stats(index: OntologyIndex) -> None:
    print(f"Total entities: {index.size}")
    print(f"Domains: {len(index.list_domains())}")
    for d in index.list_domains():
        entities = index.list_entities(domain=d)
        print(f"  {d}: {len(entities)} entities")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ontology query CLI demo")
    parser.add_argument("--vault", type=Path, default=Path("output/vault"), help="Vault path")
    sub = parser.add_subparsers(dest="command")

    p_entity = sub.add_parser("entity", help="Get entity details")
    p_entity.add_argument("name", help="Entity label or API name")

    p_domain = sub.add_parser("domain", help="List entities in domain")
    p_domain.add_argument("name", help="Domain name")

    p_traverse = sub.add_parser("traverse", help="Traverse relationships")
    p_traverse.add_argument("name", help="Starting entity")
    p_traverse.add_argument("--depth", type=int, default=2)

    p_resolve = sub.add_parser("resolve", help="Resolve source for entity")
    p_resolve.add_argument("name", help="Entity name")

    p_chain = sub.add_parser("resolve-chain", help="Resolve sources for entity + connected entities")
    p_chain.add_argument("name", help="Starting entity")
    p_chain.add_argument("--depth", type=int, default=1)

    sub.add_parser("domains", help="List all domains")
    sub.add_parser("stats", help="Show vault statistics")

    sub.add_parser("processes", help="List all processes")

    p_bottlenecks = sub.add_parser("bottlenecks", help="Show process bottlenecks")
    p_bottlenecks.add_argument("process", help="Process ID (e.g., loan-origination)")

    p_stage = sub.add_parser("stage", help="Show stage details")
    p_stage.add_argument("process", help="Process ID")
    p_stage.add_argument("stage_name", help="Stage name")

    p_entity_stages = sub.add_parser("entity-stages", help="Show stages an entity participates in")
    p_entity_stages.add_argument("name", help="Entity label")

    args = parser.parse_args()

    if not args.vault.exists():
        print(f"Vault not found: {args.vault}", file=sys.stderr)
        sys.exit(1)

    reader = LocalVaultReader(args.vault)
    index = OntologyIndex(reader)
    search = OntologySearch(reader, index)
    resolver = SourceResolver(search)
    proc_search = ProcessSearch(reader)

    if args.command == "entity":
        cmd_entity(search, args.name)
    elif args.command == "domain":
        cmd_domain(search, args.name)
    elif args.command == "traverse":
        cmd_traverse(search, args.name, args.depth)
    elif args.command == "resolve":
        cmd_resolve(resolver, args.name)
    elif args.command == "resolve-chain":
        cmd_resolve_chain(resolver, args.name, args.depth)
    elif args.command == "domains":
        cmd_domains(index)
    elif args.command == "stats":
        cmd_stats(index)
    elif args.command == "processes":
        procs = proc_search.list_processes()
        for p in procs:
            print(f"  {p['name']}: {p['label']} ({p['stage_count']} stages, {p['cycle_time_days']}d cycle, bottleneck: {p['bottleneck_severity']})")
    elif args.command == "bottlenecks":
        bns = proc_search.get_bottlenecks(args.process)
        if not bns:
            print(f"No bottlenecks found for: {args.process}", file=sys.stderr)
        for bn in bns:
            print(f"\n  [{bn.severity.upper()}] {bn.stage_name}")
            print(f"    P90: {bn.p90_days}d | SLA: {bn.sla_target_days}d | SLA Met: {bn.sla_met_pct * 100:.0f}% | Error: {bn.error_rate * 100:.0f}%")
            print(f"    Reason: {bn.reason}")
            print(f"    Entities: {', '.join(bn.entities)}")
    elif args.command == "stage":
        stage = proc_search.get_stage(args.process, args.stage_name)
        if not stage:
            print(f"Stage not found: {args.stage_name}", file=sys.stderr)
            sys.exit(1)
        print(_json(stage))
    elif args.command == "entity-stages":
        stages = proc_search.get_entity_stages(args.name)
        if not stages:
            print(f"Entity not found in any process: {args.name}", file=sys.stderr)
        for s in stages:
            print(f"  {s['process_label']} → Stage {s['stage_order']}: {s['stage']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
