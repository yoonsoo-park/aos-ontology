"""Tests for VaultConfig and agent-assisted config generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ontology.config import DOMAIN_MAPPING, OBJECT_TIERS
from scripts.ontology.vault_config import VaultConfig
from scripts.ontology.models import SFObject, SFField, SFRelationship


class TestVaultConfig(unittest.TestCase):
    def test_from_hardcoded_domains(self):
        config = VaultConfig.from_hardcoded()
        self.assertEqual(config.domain_mapping, DOMAIN_MAPPING)

    def test_from_hardcoded_tiers(self):
        config = VaultConfig.from_hardcoded()
        for tier, objects in OBJECT_TIERS.items():
            for obj in objects:
                self.assertEqual(config.tier_ranking[obj], tier)

    def test_from_hardcoded_metadata(self):
        config = VaultConfig.from_hardcoded()
        self.assertEqual(config.generated_by, "hardcoded")
        self.assertTrue(config.generated_at)

    def test_save_load_roundtrip(self):
        config = VaultConfig(
            domain_mapping={"Obj_A": "domain-a", "Obj_B": "domain-b"},
            tier_ranking={"Obj_A": 1, "Obj_B": 2},
            generated_by="test",
            generated_at="2026-01-01T00:00:00Z",
            context="test context",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            config.save(path)

            loaded = VaultConfig.load(path)
            self.assertEqual(loaded.domain_mapping, config.domain_mapping)
            self.assertEqual(loaded.tier_ranking, config.tier_ranking)
            self.assertEqual(loaded.generated_by, "test")
            self.assertEqual(loaded.context, "test context")

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sub" / "dir" / "config.json"
            config = VaultConfig(domain_mapping={"A": "b"})
            config.save(path)
            self.assertTrue(path.exists())

    def test_load_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            path.write_text('{"domain_mapping": {"X": "y"}}')
            loaded = VaultConfig.load(path)
            self.assertEqual(loaded.domain_mapping, {"X": "y"})
            self.assertEqual(loaded.tier_ranking, {})
            self.assertEqual(loaded.generated_by, "unknown")


def _make_objects() -> dict[str, SFObject]:
    loan = SFObject(
        api_name="LLC_BI__Loan__c",
        label="Loan",
        namespace="LLC_BI",
        fields=[
            SFField(api_name="LLC_BI__Amount__c", label="Amount", type="Currency"),
            SFField(api_name="LLC_BI__Status__c", label="Status", type="Picklist"),
            SFField(api_name="LLC_BI__Account__c", label="Account", type="Lookup",
                    reference_to="Account"),
        ],
        relationships=[
            SFRelationship(
                field_api_name="LLC_BI__Account__c",
                source_object="LLC_BI__Loan__c",
                target_object="Account",
                relationship_type="Lookup",
                relationship_name="Account",
                relationship_label="Account",
            )
        ],
    )
    account = SFObject(
        api_name="Account",
        label="Account",
        fields=[
            SFField(api_name="Name", label="Name", type="Text"),
        ],
        incoming_relationships=[loan.relationships[0]],
    )
    return {"LLC_BI__Loan__c": loan, "Account": account}


class TestAgentAssistParsing(unittest.TestCase):
    def test_extract_json_from_code_block(self):
        from scripts.ontology.agent_assist import _extract_json

        text = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        result = _extract_json(text)
        self.assertEqual(result, {"key": "value"})

    def test_extract_json_bare(self):
        from scripts.ontology.agent_assist import _extract_json

        result = _extract_json('{"a": 1, "b": 2}')
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_entity_summary(self):
        from scripts.ontology.agent_assist import _entity_summary

        objects = _make_objects()
        summary = _entity_summary(objects["LLC_BI__Loan__c"], objects)
        self.assertIn("LLC_BI__Loan__c", summary)
        self.assertIn("Loan", summary)
        self.assertIn("Account", summary)

    @patch("scripts.ontology.agent_assist._call_llm")
    def test_infer_domain_mapping_mock(self, mock_llm):
        from scripts.ontology.agent_assist import infer_domain_mapping

        mock_llm.return_value = '```json\n{"LLC_BI__Loan__c": "lending", "Account": "crm"}\n```'
        objects = _make_objects()
        result = infer_domain_mapping(objects, context="test")
        self.assertEqual(result["LLC_BI__Loan__c"], "lending")
        self.assertEqual(result["Account"], "crm")
        mock_llm.assert_called_once()

    @patch("scripts.ontology.agent_assist._call_llm")
    def test_infer_tier_ranking_mock(self, mock_llm):
        from scripts.ontology.agent_assist import infer_tier_ranking

        mock_llm.return_value = '```json\n{"Account": 1, "LLC_BI__Loan__c": 1}\n```'
        objects = _make_objects()
        result = infer_tier_ranking(objects)
        self.assertEqual(result["Account"], 1)
        self.assertEqual(result["LLC_BI__Loan__c"], 1)

    @patch("scripts.ontology.agent_assist._call_llm")
    def test_infer_tier_ranking_fallback_on_error(self, mock_llm):
        from scripts.ontology.agent_assist import infer_tier_ranking

        mock_llm.side_effect = Exception("API error")
        objects = _make_objects()
        result = infer_tier_ranking(objects)
        self.assertEqual(len(result), 2)
        for v in result.values():
            self.assertIn(v, [1, 2, 3])

    @patch("scripts.ontology.agent_assist._call_llm")
    def test_generate_vault_config_mock(self, mock_llm):
        from scripts.ontology.agent_assist import generate_vault_config

        mock_llm.side_effect = [
            '```json\n{"LLC_BI__Loan__c": "lending", "Account": "crm"}\n```',
            '```json\n{"LLC_BI__Loan__c": 1, "Account": 1}\n```',
        ]
        objects = _make_objects()
        config = generate_vault_config(objects, context="test")
        self.assertEqual(config.generated_by, "agent")
        self.assertEqual(config.domain_mapping["LLC_BI__Loan__c"], "lending")
        self.assertEqual(config.tier_ranking["Account"], 1)


class TestGenerateVaultWithConfig(unittest.TestCase):
    def test_entity_note_uses_vault_config(self):
        from scripts.ontology.generate_vault import generate_entity_note

        objects = _make_objects()
        config = VaultConfig(
            domain_mapping={"LLC_BI__Loan__c": "custom-domain"},
            tier_ranking={"LLC_BI__Loan__c": 99},
        )
        note = generate_entity_note(objects["LLC_BI__Loan__c"], objects, config)
        self.assertIn("domain: custom-domain", note)
        self.assertIn("tier: 99", note)

    def test_entity_note_without_config_uses_hardcoded(self):
        from scripts.ontology.generate_vault import generate_entity_note

        objects = _make_objects()
        note = generate_entity_note(objects["LLC_BI__Loan__c"], objects)
        self.assertIn("domain: loan-origination", note)


if __name__ == "__main__":
    unittest.main()
