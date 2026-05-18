"""Build OntologyGraph from SFObjects + ProcessConfigs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import DOMAIN_MAPPING
from .graph_model import Edge, EdgeType, Node, NodeType, OntologyGraph
from .models import SFObject
from .process_models import ProcessConfig
from .vault_config import VaultConfig


def _entity_node_id(api_name: str) -> str:
    return f"entity::{api_name}"


def _process_node_id(process_key: str) -> str:
    return f"process::{process_key}"


def _stage_node_id(process_key: str, stage_key: str) -> str:
    return f"stage::{process_key}::{stage_key}"


def _domain_node_id(domain_key: str) -> str:
    return f"domain::{domain_key}"


def _obj_label(api_name: str, objects: dict[str, SFObject]) -> str:
    obj = objects.get(api_name)
    if obj:
        return obj.clean_label
    name = api_name
    for ns in ("LLC_BI__", "nFORCE__", "nFORMS__", "nSBA__", "FinServ__"):
        name = name.removeprefix(ns)
    return name.removesuffix("__c").removesuffix("__mdt").replace("_", " ")


def build_graph(
    objects: dict[str, SFObject],
    process_configs: dict[str, ProcessConfig],
    vault_config: VaultConfig | None = None,
) -> OntologyGraph:
    graph = OntologyGraph(
        version="1.0.0",
        metadata={
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": "aos-ontology",
        },
    )

    dm = vault_config.domain_mapping if vault_config else DOMAIN_MAPPING
    tr = vault_config.tier_ranking if vault_config else {}

    seen_domains: set[str] = set()

    # --- Entity nodes + domain membership edges ---
    for api_name, obj in objects.items():
        domain = dm.get(api_name, "uncategorized")
        tier = tr.get(api_name, 0)

        graph.nodes.append(Node(
            id=_entity_node_id(api_name),
            node_type=NodeType.ENTITY,
            label=obj.clean_label,
            properties={
                "api_name": api_name,
                "namespace": obj.namespace or "standard",
                "domain": domain,
                "tier": tier,
                "field_count": len(obj.fields),
                "description": obj.description or "",
            },
        ))

        if domain != "uncategorized":
            if domain not in seen_domains:
                seen_domains.add(domain)
                graph.nodes.append(Node(
                    id=_domain_node_id(domain),
                    node_type=NodeType.DOMAIN,
                    label=domain.replace("-", " ").title(),
                    properties={"domain_key": domain},
                ))

            graph.edges.append(Edge(
                id=f"domain_member::{api_name}::{domain}",
                edge_type=EdgeType.DOMAIN_MEMBERSHIP,
                source=_entity_node_id(api_name),
                target=_domain_node_id(domain),
                properties={"tier": tier},
            ))

    # --- SF relationship edges ---
    for api_name, obj in objects.items():
        for rel in obj.relationships:
            if rel.target_object not in objects:
                continue
            graph.edges.append(Edge(
                id=f"sf_rel::{rel.source_object}::{rel.target_object}::{rel.field_api_name}",
                edge_type=EdgeType.SF_RELATIONSHIP,
                source=_entity_node_id(rel.source_object),
                target=_entity_node_id(rel.target_object),
                label=f"{_obj_label(rel.target_object, objects)} ({rel.relationship_type})",
                properties={
                    "field_api_name": rel.field_api_name,
                    "relationship_type": rel.relationship_type,
                    "relationship_name": rel.relationship_name,
                    "delete_constraint": rel.delete_constraint,
                },
            ))

    # --- Process + stage nodes + edges ---
    for process_key, proc in process_configs.items():
        graph.nodes.append(Node(
            id=_process_node_id(process_key),
            node_type=NodeType.PROCESS,
            label=proc.name,
            properties={
                "process_key": process_key,
                "source_object": proc.source_object,
                "stage_field": proc.stage_field,
                "domain": proc.process_key.split("-")[0] if "-" in proc.process_key else proc.process_key,
                "description": proc.description,
            },
        ))

        for stage in proc.stages:
            graph.nodes.append(Node(
                id=_stage_node_id(process_key, stage.stage_key),
                node_type=NodeType.STAGE,
                label=stage.name,
                properties={
                    "process_key": process_key,
                    "stage_key": stage.stage_key,
                    "order": stage.order,
                    "stage_type": stage.stage_type.value,
                    "description": stage.description,
                },
            ))

            # process_contains edge
            graph.edges.append(Edge(
                id=f"contains::{process_key}::{stage.stage_key}",
                edge_type=EdgeType.PROCESS_CONTAINS,
                source=_process_node_id(process_key),
                target=_stage_node_id(process_key, stage.stage_key),
                properties={"order": stage.order},
            ))

            # stage_transition edges
            transition_type = "parallel" if stage.stage_type.value == "parallel" else "sequential"
            for succ_key in stage.successors:
                graph.edges.append(Edge(
                    id=f"transition::{process_key}::{stage.stage_key}::{succ_key}",
                    edge_type=EdgeType.STAGE_TRANSITION,
                    source=_stage_node_id(process_key, stage.stage_key),
                    target=_stage_node_id(process_key, succ_key),
                    properties={"transition_type": transition_type},
                ))

            # stage_involvement edges
            for ent in stage.involved_entities:
                entity_id = _entity_node_id(ent.api_name)
                if graph.node_by_id(entity_id) is not None:
                    graph.edges.append(Edge(
                        id=f"involvement::{process_key}::{stage.stage_key}::{ent.api_name}",
                        edge_type=EdgeType.STAGE_INVOLVEMENT,
                        source=entity_id,
                        target=_stage_node_id(process_key, stage.stage_key),
                        label=ent.role,
                        properties={
                            "role": ent.role,
                            "relevant_fields": ent.relevant_fields,
                        },
                    ))

    # --- Update metadata ---
    graph.metadata["entity_count"] = len(graph.nodes_by_type(NodeType.ENTITY))
    graph.metadata["process_count"] = len(graph.nodes_by_type(NodeType.PROCESS))
    graph.metadata["stage_count"] = len(graph.nodes_by_type(NodeType.STAGE))
    graph.metadata["domain_count"] = len(graph.nodes_by_type(NodeType.DOMAIN))
    graph.metadata["edge_count"] = len(graph.edges)

    return graph
