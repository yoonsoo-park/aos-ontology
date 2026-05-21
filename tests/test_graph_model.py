"""Tests for unified graph model, builder, config loader, and metrics."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.ontology.graph_model import (
    Edge,
    EdgeType,
    Node,
    NodeType,
    OntologyGraph,
)
from scripts.ontology.graph_builder import build_graph
from scripts.ontology.generate_graph import write_graph
from scripts.ontology.metrics import SyntheticMetricsAdapter
from scripts.ontology.process_config_loader import load_all_process_configs, load_process_config
from scripts.ontology.process_models import ProcessConfig, StageType
from scripts.ontology.models import SFObject, SFField, SFRelationship


CONFIGS_DIR = Path(__file__).parent.parent / "configs" / "processes"


# --- Graph Model ---

class TestGraphModel(unittest.TestCase):
    def test_node_roundtrip(self):
        node = Node(id="entity::Test", node_type=NodeType.ENTITY, label="Test",
                     properties={"api_name": "Test__c"})
        d = node.to_dict()
        restored = Node.from_dict(d)
        self.assertEqual(restored.id, node.id)
        self.assertEqual(restored.node_type, NodeType.ENTITY)
        self.assertEqual(restored.properties["api_name"], "Test__c")

    def test_edge_roundtrip(self):
        edge = Edge(id="sf_rel::A::B::f", edge_type=EdgeType.SF_RELATIONSHIP,
                     source="entity::A", target="entity::B", label="B (Lookup)",
                     properties={"relationship_type": "Lookup"})
        d = edge.to_dict()
        restored = Edge.from_dict(d)
        self.assertEqual(restored.id, edge.id)
        self.assertEqual(restored.edge_type, EdgeType.SF_RELATIONSHIP)
        self.assertEqual(restored.properties["relationship_type"], "Lookup")

    def test_graph_roundtrip(self):
        graph = OntologyGraph(version="1.0.0")
        graph.nodes.append(Node(id="entity::A", node_type=NodeType.ENTITY, label="A"))
        graph.nodes.append(Node(id="entity::B", node_type=NodeType.ENTITY, label="B"))
        graph.edges.append(Edge(id="sf_rel::A::B::f", edge_type=EdgeType.SF_RELATIONSHIP,
                                source="entity::A", target="entity::B"))
        d = graph.to_dict()
        restored = OntologyGraph.from_dict(d)
        self.assertEqual(len(restored.nodes), 2)
        self.assertEqual(len(restored.edges), 1)
        self.assertEqual(restored.version, "1.0.0")

    def test_graph_lookup_helpers(self):
        graph = OntologyGraph()
        graph.nodes.append(Node(id="entity::A", node_type=NodeType.ENTITY, label="A"))
        graph.nodes.append(Node(id="stage::p::s1", node_type=NodeType.STAGE, label="S1"))
        graph.edges.append(Edge(id="e1", edge_type=EdgeType.SF_RELATIONSHIP,
                                source="entity::A", target="entity::B"))
        graph.edges.append(Edge(id="e2", edge_type=EdgeType.STAGE_INVOLVEMENT,
                                source="entity::A", target="stage::p::s1"))

        self.assertIsNotNone(graph.node_by_id("entity::A"))
        self.assertIsNone(graph.node_by_id("entity::Z"))
        self.assertEqual(len(graph.nodes_by_type(NodeType.ENTITY)), 1)
        self.assertEqual(len(graph.edges_from("entity::A")), 2)
        self.assertEqual(len(graph.edges_from("entity::A", EdgeType.SF_RELATIONSHIP)), 1)
        self.assertEqual(len(graph.edges_to("stage::p::s1")), 1)


# --- Config Loader ---

class TestProcessConfigLoader(unittest.TestCase):
    def test_load_loan_origination(self):
        cfg = load_process_config(CONFIGS_DIR / "loan-origination.json")
        self.assertEqual(cfg.process_key, "loan-origination")
        self.assertEqual(cfg.source_object, "LLC_BI__Loan__c")
        self.assertEqual(len(cfg.stages), 18)

    def test_load_all(self):
        configs = load_all_process_configs(CONFIGS_DIR)
        self.assertIn("loan-origination", configs)
        self.assertIsInstance(configs["loan-origination"], ProcessConfig)

    def test_missing_dir_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_all_process_configs(Path("/nonexistent/dir"))

    def test_empty_dir_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                load_all_process_configs(Path(tmpdir))

    def test_stage_types(self):
        cfg = load_process_config(CONFIGS_DIR / "loan-origination.json")
        seq = [s for s in cfg.stages if s.stage_type == StageType.SEQUENTIAL]
        par = [s for s in cfg.stages if s.stage_type == StageType.PARALLEL]
        pc = [s for s in cfg.stages if s.stage_type == StageType.POST_CLOSE]
        self.assertEqual(len(seq), 12)
        self.assertEqual(len(par), 3)
        self.assertEqual(len(pc), 3)

    def test_stage_metrics(self):
        cfg = load_process_config(CONFIGS_DIR / "loan-origination.json")
        credit = next(s for s in cfg.stages if s.stage_key == "credit_underwriting")
        self.assertEqual(credit.metrics.avg_days, 5.0)
        self.assertEqual(credit.metrics.p90_days, 10.0)
        self.assertEqual(credit.metrics.sla_target_days, 5.0)

    def test_stage_successors(self):
        cfg = load_process_config(CONFIGS_DIR / "loan-origination.json")
        qual = next(s for s in cfg.stages if s.stage_key == "qualification")
        self.assertEqual(qual.successors, ["proposal"])

    def test_involved_entities(self):
        cfg = load_process_config(CONFIGS_DIR / "loan-origination.json")
        credit = next(s for s in cfg.stages if s.stage_key == "credit_underwriting")
        api_names = [e.api_name for e in credit.involved_entities]
        self.assertIn("LLC_BI__Loan__c", api_names)
        self.assertIn("LLC_BI__Credit_Memo__c", api_names)


# --- Graph Builder ---

def _make_test_objects() -> dict[str, SFObject]:
    loan = SFObject(
        api_name="LLC_BI__Loan__c", label="LLC_BI Loan", namespace="LLC_BI",
        fields=[SFField(api_name="LLC_BI__Amount__c", label="Amount", type="Currency")],
        relationships=[
            SFRelationship(
                field_api_name="LLC_BI__Account__c",
                source_object="LLC_BI__Loan__c",
                target_object="Account",
                relationship_type="Lookup",
                relationship_name="LLC_BI__Account__r",
                relationship_label="Account",
            )
        ],
    )
    account = SFObject(
        api_name="Account", label="Account",
        fields=[SFField(api_name="Name", label="Name", type="Text")],
    )
    return {"LLC_BI__Loan__c": loan, "Account": account}


class TestGraphBuilder(unittest.TestCase):
    def test_builds_entity_nodes(self):
        objects = _make_test_objects()
        configs = load_all_process_configs(CONFIGS_DIR)
        graph = build_graph(objects, configs)
        entities = graph.nodes_by_type(NodeType.ENTITY)
        self.assertEqual(len(entities), 2)

    def test_builds_sf_relationship_edges(self):
        objects = _make_test_objects()
        graph = build_graph(objects, {})
        sf_edges = graph.edges_by_type(EdgeType.SF_RELATIONSHIP)
        self.assertEqual(len(sf_edges), 1)
        self.assertEqual(sf_edges[0].source, "entity::LLC_BI__Loan__c")
        self.assertEqual(sf_edges[0].target, "entity::Account")

    def test_builds_process_and_stages(self):
        objects = _make_test_objects()
        configs = load_all_process_configs(CONFIGS_DIR)
        graph = build_graph(objects, configs)
        processes = graph.nodes_by_type(NodeType.PROCESS)
        stages = graph.nodes_by_type(NodeType.STAGE)
        self.assertEqual(len(processes), len(configs))
        self.assertGreaterEqual(len(stages), 18)

    def test_builds_stage_transitions(self):
        objects = _make_test_objects()
        configs = load_all_process_configs(CONFIGS_DIR)
        graph = build_graph(objects, configs)
        transitions = graph.edges_by_type(EdgeType.STAGE_TRANSITION)
        self.assertGreater(len(transitions), 15)

    def test_builds_stage_involvements(self):
        objects = _make_test_objects()
        configs = load_all_process_configs(CONFIGS_DIR)
        graph = build_graph(objects, configs)
        involvements = graph.edges_by_type(EdgeType.STAGE_INVOLVEMENT)
        self.assertGreater(len(involvements), 0)
        loan_involvements = [e for e in involvements if e.source == "entity::LLC_BI__Loan__c"]
        self.assertGreater(len(loan_involvements), 5)

    def test_builds_contains_edges(self):
        objects = _make_test_objects()
        configs = load_all_process_configs(CONFIGS_DIR)
        graph = build_graph(objects, configs)
        contains = graph.edges_by_type(EdgeType.PROCESS_CONTAINS)
        total_stages = sum(len(c.stages) for c in configs.values())
        self.assertEqual(len(contains), total_stages)

    def test_metadata_counts(self):
        objects = _make_test_objects()
        configs = load_all_process_configs(CONFIGS_DIR)
        graph = build_graph(objects, configs)
        self.assertEqual(graph.metadata["entity_count"], 2)
        self.assertEqual(graph.metadata["process_count"], len(configs))
        total_stages = sum(len(c.stages) for c in configs.values())
        self.assertEqual(graph.metadata["stage_count"], total_stages)


# --- Graph Serialization ---

class TestGenerateGraph(unittest.TestCase):
    def test_writes_graph_json(self):
        objects = _make_test_objects()
        configs = load_all_process_configs(CONFIGS_DIR)
        graph = build_graph(objects, configs)

        with tempfile.TemporaryDirectory() as tmpdir:
            stats = write_graph(graph, Path(tmpdir))
            graph_path = Path(tmpdir) / "_meta" / "graph.json"
            self.assertTrue(graph_path.exists())
            data = json.loads(graph_path.read_text())
            self.assertIn("nodes", data)
            self.assertIn("edges", data)
            self.assertGreater(len(data["nodes"]), 0)

    def test_writes_metrics_overlay(self):
        configs = load_all_process_configs(CONFIGS_DIR)
        graph = build_graph({}, configs)
        adapter = SyntheticMetricsAdapter(configs)

        with tempfile.TemporaryDirectory() as tmpdir:
            stats = write_graph(graph, Path(tmpdir),
                                metrics_adapter=adapter,
                                process_keys=list(configs.keys()))
            self.assertEqual(stats["metrics_files"], len(configs))
            metrics_path = Path(tmpdir) / "_meta" / "metrics" / "loan-origination.json"
            self.assertTrue(metrics_path.exists())
            data = json.loads(metrics_path.read_text())
            self.assertEqual(data["adapter"], "synthetic")
            self.assertEqual(len(data["stages"]), 18)
            self.assertIn("qualification", data["stages"])


# --- Metrics Adapter ---

class TestSyntheticMetricsAdapter(unittest.TestCase):
    def test_fetch_metrics(self):
        configs = load_all_process_configs(CONFIGS_DIR)
        adapter = SyntheticMetricsAdapter(configs)
        metrics = adapter.fetch_metrics("loan-origination")
        self.assertEqual(len(metrics), 18)
        self.assertEqual(adapter.adapter_name(), "synthetic")

    def test_metrics_values(self):
        configs = load_all_process_configs(CONFIGS_DIR)
        adapter = SyntheticMetricsAdapter(configs)
        metrics = adapter.fetch_metrics("loan-origination")
        credit = next(m for m in metrics if m.stage_key == "credit_underwriting")
        self.assertEqual(credit.avg_days, 5.0)
        self.assertEqual(credit.bottleneck_severity, "critical")

    def test_missing_process(self):
        configs = load_all_process_configs(CONFIGS_DIR)
        adapter = SyntheticMetricsAdapter(configs)
        metrics = adapter.fetch_metrics("nonexistent")
        self.assertEqual(len(metrics), 0)


if __name__ == "__main__":
    unittest.main()
