"""Unified graph model for AOS Ontology — portable to Obsidian, neo4j, or any graph consumer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    ENTITY = "entity"
    PROCESS = "process"
    STAGE = "stage"
    DOMAIN = "domain"


class EdgeType(str, Enum):
    SF_RELATIONSHIP = "sf_relationship"
    STAGE_TRANSITION = "stage_transition"
    STAGE_INVOLVEMENT = "stage_involvement"
    DOMAIN_MEMBERSHIP = "domain_membership"
    PROCESS_CONTAINS = "process_contains"


@dataclass
class Node:
    id: str
    node_type: NodeType
    label: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "label": self.label,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        return cls(
            id=data["id"],
            node_type=NodeType(data["node_type"]),
            label=data["label"],
            properties=data.get("properties", {}),
        )


@dataclass
class Edge:
    id: str
    edge_type: EdgeType
    source: str
    target: str
    label: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "edge_type": self.edge_type.value,
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Edge:
        return cls(
            id=data["id"],
            edge_type=EdgeType(data["edge_type"]),
            source=data["source"],
            target=data["target"],
            label=data.get("label", ""),
            properties=data.get("properties", {}),
        )


@dataclass
class OntologyGraph:
    version: str = "1.0.0"
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def node_by_id(self, node_id: str) -> Node | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def nodes_by_type(self, node_type: NodeType) -> list[Node]:
        return [n for n in self.nodes if n.node_type == node_type]

    def edges_by_type(self, edge_type: EdgeType) -> list[Edge]:
        return [e for e in self.edges if e.edge_type == edge_type]

    def edges_from(self, node_id: str, edge_type: EdgeType | None = None) -> list[Edge]:
        edges = [e for e in self.edges if e.source == node_id]
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges

    def edges_to(self, node_id: str, edge_type: EdgeType | None = None) -> list[Edge]:
        edges = [e for e in self.edges if e.target == node_id]
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "metadata": self.metadata,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OntologyGraph:
        return cls(
            version=data.get("version", "1.0.0"),
            metadata=data.get("metadata", {}),
            nodes=[Node.from_dict(n) for n in data.get("nodes", [])],
            edges=[Edge.from_dict(e) for e in data.get("edges", [])],
        )
