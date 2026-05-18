"""Tests for agent-assisted process config generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ontology.models import SFField, SFObject, SFPicklistValue, SFRelationship
from scripts.ontology.process_agent import (
    ProcessCandidate,
    _get_related_objects,
    _slugify,
    _validate_entity_involvement,
    _validate_metrics,
    _validate_stage_structure,
    discover_process_candidates,
    save_process_config,
)
from scripts.ontology.process_config_loader import load_process_config


def _make_objects() -> dict[str, SFObject]:
    loan = SFObject(
        api_name="LLC_BI__Loan__c", label="Loan", namespace="LLC_BI",
        fields=[
            SFField(api_name="LLC_BI__Stage__c", label="Stage", type="Picklist",
                    description="Tracks the loan lifecycle stage",
                    picklist_values=[
                        SFPicklistValue(api_name="Qualification", label="Qualification"),
                        SFPicklistValue(api_name="Proposal", label="Proposal"),
                        SFPicklistValue(api_name="Application", label="Application"),
                        SFPicklistValue(api_name="Underwriting", label="Underwriting"),
                        SFPicklistValue(api_name="Closing", label="Closing"),
                    ]),
            SFField(api_name="LLC_BI__Amount__c", label="Amount", type="Currency"),
        ],
        relationships=[
            SFRelationship(
                field_api_name="LLC_BI__Account__c",
                source_object="LLC_BI__Loan__c",
                target_object="Account",
                relationship_type="Lookup",
                relationship_name="LLC_BI__Account__r",
                relationship_label="Account",
            ),
            SFRelationship(
                field_api_name="LLC_BI__Product__c",
                source_object="LLC_BI__Loan__c",
                target_object="LLC_BI__Product__c",
                relationship_type="Lookup",
                relationship_name="LLC_BI__Product__r",
                relationship_label="Product",
            ),
        ],
        incoming_relationships=[
            SFRelationship(field_api_name=f"f{i}", source_object=f"Child{i}__c",
                           target_object="LLC_BI__Loan__c", relationship_type="Lookup",
                           relationship_name=f"r{i}", relationship_label=f"R{i}")
            for i in range(6)
        ],
    )
    account = SFObject(
        api_name="Account", label="Account",
        fields=[SFField(api_name="Name", label="Name", type="Text")],
        incoming_relationships=[
            SFRelationship(field_api_name="LLC_BI__Account__c",
                           source_object="LLC_BI__Loan__c", target_object="Account",
                           relationship_type="Lookup", relationship_name="r", relationship_label="R"),
        ],
    )
    product = SFObject(
        api_name="LLC_BI__Product__c", label="Product", namespace="LLC_BI",
        fields=[SFField(api_name="Name", label="Name", type="Text")],
    )
    low_degree = SFObject(
        api_name="LLC_BI__Minor__c", label="Minor", namespace="LLC_BI",
        fields=[
            SFField(api_name="LLC_BI__Status__c", label="Status", type="Picklist",
                    description="Status field",
                    picklist_values=[
                        SFPicklistValue(api_name="Open", label="Open"),
                        SFPicklistValue(api_name="Closed", label="Closed"),
                    ]),
        ],
    )
    children = {}
    for i in range(6):
        children[f"Child{i}__c"] = SFObject(
            api_name=f"Child{i}__c", label=f"Child {i}",
            relationships=[
                SFRelationship(field_api_name=f"Loan__c", source_object=f"Child{i}__c",
                               target_object="LLC_BI__Loan__c", relationship_type="Lookup",
                               relationship_name=f"Loan__r", relationship_label="Loan"),
            ],
        )
    return {
        "LLC_BI__Loan__c": loan,
        "Account": account,
        "LLC_BI__Product__c": product,
        "LLC_BI__Minor__c": low_degree,
        **children,
    }


class TestDiscoverCandidates(unittest.TestCase):
    def test_finds_stage_picklist(self):
        objects = _make_objects()
        candidates = discover_process_candidates(objects)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source_object, "LLC_BI__Loan__c")
        self.assertEqual(candidates[0].stage_field, "LLC_BI__Stage__c")
        self.assertEqual(len(candidates[0].picklist_values), 5)

    def test_filters_low_centrality(self):
        objects = _make_objects()
        candidates = discover_process_candidates(objects)
        source_objects = [c.source_object for c in candidates]
        self.assertNotIn("LLC_BI__Minor__c", source_objects)

    def test_sets_domain_from_mapping(self):
        objects = _make_objects()
        candidates = discover_process_candidates(
            objects, domain_mapping={"LLC_BI__Loan__c": "loan-origination"},
        )
        self.assertEqual(candidates[0].domain, "loan-origination")

    def test_no_candidates_without_stage_field(self):
        objects = {"Account": _make_objects()["Account"]}
        candidates = discover_process_candidates(objects)
        self.assertEqual(len(candidates), 0)


class TestGetRelatedObjects(unittest.TestCase):
    def test_includes_direct_relationships(self):
        objects = _make_objects()
        related = _get_related_objects("LLC_BI__Loan__c", objects)
        self.assertIn("LLC_BI__Loan__c", related)
        self.assertIn("Account", related)
        self.assertIn("LLC_BI__Product__c", related)

    def test_missing_source_returns_empty(self):
        objects = _make_objects()
        related = _get_related_objects("Nonexistent__c", objects)
        self.assertEqual(len(related), 0)

    def test_respects_max_objects(self):
        objects = _make_objects()
        related = _get_related_objects("LLC_BI__Loan__c", objects, max_objects=2)
        self.assertLessEqual(len(related), 2)

    def test_source_always_included(self):
        objects = _make_objects()
        related = _get_related_objects("LLC_BI__Loan__c", objects, max_objects=1)
        self.assertIn("LLC_BI__Loan__c", related)


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_slugify("Credit Underwriting"), "credit_underwriting")

    def test_special_chars(self):
        self.assertEqual(_slugify("Doc Prep & Review"), "doc_prep_review")

    def test_already_slug(self):
        self.assertEqual(_slugify("qualification"), "qualification")


class TestValidateStageStructure(unittest.TestCase):
    def test_fixes_invalid_stage_type(self):
        data = {"stages": [
            {"name": "Test", "stage_key": "test", "stage_type": "invalid",
             "predecessors": [], "successors": []},
        ]}
        result = _validate_stage_structure(data, {"Test"})
        self.assertEqual(result["stages"][0]["stage_type"], "sequential")

    def test_removes_invalid_successors(self):
        data = {"stages": [
            {"name": "A", "stage_key": "a", "stage_type": "sequential",
             "predecessors": [], "successors": ["nonexistent"]},
        ]}
        result = _validate_stage_structure(data, {"A"})
        self.assertEqual(result["stages"][0]["successors"], [])


class TestValidateEntityInvolvement(unittest.TestCase):
    def test_removes_invalid_entities(self):
        involvement = {
            "stage_a": [
                {"api_name": "Account", "role": "primary", "relevant_fields": ["Name"]},
                {"api_name": "Fake__c", "role": "primary", "relevant_fields": []},
            ],
        }
        result = _validate_entity_involvement(involvement, {"Account"})
        self.assertEqual(len(result["stage_a"]), 1)
        self.assertEqual(result["stage_a"][0]["api_name"], "Account")

    def test_fixes_invalid_role(self):
        involvement = {
            "stage_a": [
                {"api_name": "Account", "role": "secondary", "relevant_fields": []},
            ],
        }
        result = _validate_entity_involvement(involvement, {"Account"})
        self.assertEqual(result["stage_a"][0]["role"], "reference")

    def test_truncates_relevant_fields(self):
        involvement = {
            "stage_a": [
                {"api_name": "Account", "role": "primary",
                 "relevant_fields": ["a", "b", "c", "d", "e", "f"]},
            ],
        }
        result = _validate_entity_involvement(involvement, {"Account"})
        self.assertEqual(len(result["stage_a"][0]["relevant_fields"]), 4)


class TestValidateMetrics(unittest.TestCase):
    def test_clamps_p50_avg_p90(self):
        metrics = {"a": {"p50_days": 5.0, "avg_days": 3.0, "p90_days": 2.0,
                         "entry_count": 100, "exit_count": 90,
                         "error_rate": 0.05, "rework_rate": 0.03,
                         "sla_met_pct": 0.8, "bottleneck_severity": "none"}}
        result = _validate_metrics(metrics, ["a"])
        self.assertLessEqual(result["a"]["p50_days"], result["a"]["avg_days"])
        self.assertLessEqual(result["a"]["avg_days"], result["a"]["p90_days"])

    def test_enforces_monotonic_entry_count(self):
        metrics = {
            "a": {"entry_count": 1000, "exit_count": 800, "p50_days": 1, "avg_days": 2, "p90_days": 3,
                   "error_rate": 0.05, "rework_rate": 0.03, "sla_met_pct": 0.8, "bottleneck_severity": "none"},
            "b": {"entry_count": 900, "exit_count": 850, "p50_days": 1, "avg_days": 2, "p90_days": 3,
                   "error_rate": 0.05, "rework_rate": 0.03, "sla_met_pct": 0.8, "bottleneck_severity": "none"},
        }
        result = _validate_metrics(metrics, ["a", "b"])
        self.assertLessEqual(result["b"]["entry_count"], result["a"]["exit_count"])

    def test_exit_lte_entry(self):
        metrics = {"a": {"entry_count": 100, "exit_count": 200, "p50_days": 1, "avg_days": 2, "p90_days": 3,
                         "error_rate": 0.05, "rework_rate": 0.03, "sla_met_pct": 0.8, "bottleneck_severity": "none"}}
        result = _validate_metrics(metrics, ["a"])
        self.assertLessEqual(result["a"]["exit_count"], result["a"]["entry_count"])

    def test_fixes_invalid_severity(self):
        metrics = {"a": {"entry_count": 100, "exit_count": 90, "p50_days": 1, "avg_days": 2, "p90_days": 3,
                         "error_rate": 0.05, "rework_rate": 0.03, "sla_met_pct": 0.8, "bottleneck_severity": "extreme"}}
        result = _validate_metrics(metrics, ["a"])
        self.assertEqual(result["a"]["bottleneck_severity"], "none")


class TestSaveProcessConfig(unittest.TestCase):
    def test_saves_and_loads(self):
        config = {
            "name": "Test Process",
            "process_key": "test-process",
            "description": "A test",
            "domain": "test",
            "source_object": "Test__c",
            "stage_field": "Stage__c",
            "metrics_source": "synthetic",
            "stages": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_process_config(config, Path(tmpdir))
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertEqual(data["process_key"], "test-process")


class TestGenerateRoundtrip(unittest.TestCase):
    @patch("scripts.ontology.process_agent._call_llm")
    def test_generate_produces_loadable_config(self, mock_llm):
        from scripts.ontology.process_agent import generate_process_config

        structure_response = json.dumps({
            "name": "Test Origination",
            "process_key": "test-origination",
            "description": "Test workflow",
            "domain": "test",
            "source_object": "LLC_BI__Loan__c",
            "stage_field": "LLC_BI__Stage__c",
            "metrics_source": "synthetic",
            "stages": [
                {"name": "Qualification", "stage_key": "qualification", "order": 1,
                 "stage_type": "sequential", "description": "Initial check",
                 "predecessors": [], "successors": ["review"],
                 "sla_target_days": 2.0},
                {"name": "Review", "stage_key": "review", "order": 2,
                 "stage_type": "sequential", "description": "Final review",
                 "predecessors": ["qualification"], "successors": [],
                 "sla_target_days": 3.0},
            ],
        })

        involvement_response = json.dumps({
            "qualification": [
                {"api_name": "Account", "role": "primary", "relevant_fields": ["Name"]},
            ],
            "review": [
                {"api_name": "LLC_BI__Loan__c", "role": "primary", "relevant_fields": ["LLC_BI__Amount__c"]},
            ],
        })

        metrics_response = json.dumps({
            "qualification": {
                "avg_days": 1.5, "p50_days": 1.0, "p90_days": 3.0,
                "entry_count": 1000, "exit_count": 800,
                "error_rate": 0.03, "rework_rate": 0.02,
                "sla_target_days": 2.0, "sla_met_pct": 0.90,
                "bottleneck_severity": "none",
            },
            "review": {
                "avg_days": 2.0, "p50_days": 1.5, "p90_days": 4.0,
                "entry_count": 800, "exit_count": 750,
                "error_rate": 0.05, "rework_rate": 0.04,
                "sla_target_days": 3.0, "sla_met_pct": 0.85,
                "bottleneck_severity": "low",
            },
        })

        mock_llm.side_effect = [
            f"```json\n{structure_response}\n```",
            f"```json\n{involvement_response}\n```",
            f"```json\n{metrics_response}\n```",
        ]

        objects = _make_objects()
        candidate = ProcessCandidate(
            source_object="LLC_BI__Loan__c",
            stage_field="LLC_BI__Stage__c",
            picklist_values=[
                SFPicklistValue(api_name="Qualification", label="Qualification"),
                SFPicklistValue(api_name="Review", label="Review"),
            ],
            domain="test",
        )

        config = generate_process_config(candidate, objects)

        self.assertEqual(config["process_key"], "test-origination")
        self.assertEqual(len(config["stages"]), 2)
        self.assertEqual(config["stages"][0]["involved_entities"][0]["api_name"], "Account")
        self.assertIn("synthetic_metrics", config["stages"][0])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test-origination.json"
            path.write_text(json.dumps(config, indent=2))
            loaded = load_process_config(path)
            self.assertEqual(loaded.process_key, "test-origination")
            self.assertEqual(len(loaded.stages), 2)
            self.assertEqual(loaded.stages[0].metrics.avg_days, 1.5)


if __name__ == "__main__":
    unittest.main()
