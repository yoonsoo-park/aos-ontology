"""Tests for ontology_query library using the generated vault."""

from __future__ import annotations

import unittest
from pathlib import Path

from ontology_query.reader import LocalVaultReader
from ontology_query.index import OntologyIndex
from ontology_query.search import OntologySearch
from ontology_query.resolver import SourceResolver
from ontology_query.frontmatter import parse_frontmatter

VAULT_PATH = Path(__file__).parent.parent / "output" / "vault"


def _has_vault() -> bool:
    return (VAULT_PATH / "_meta" / "index.json").exists()


@unittest.skipUnless(_has_vault(), "Generated vault not found at output/vault")
class TestLocalVaultReader(unittest.TestCase):
    def setUp(self):
        self.reader = LocalVaultReader(VAULT_PATH)

    def test_read_file(self):
        content = self.reader.read_file("_meta/index.json")
        self.assertIn("LLC_BI__Loan__c", content)

    def test_list_files_entities(self):
        files = self.reader.list_files("entities")
        self.assertGreater(len(files), 20)
        self.assertTrue(any("Loan.md" in f for f in files))

    def test_list_files_domains(self):
        files = self.reader.list_files("domains")
        self.assertGreater(len(files), 5)

    def test_file_exists(self):
        self.assertTrue(self.reader.file_exists("entities/Loan.md"))
        self.assertFalse(self.reader.file_exists("entities/NonExistent.md"))


@unittest.skipUnless(_has_vault(), "Generated vault not found at output/vault")
class TestOntologyIndex(unittest.TestCase):
    def setUp(self):
        reader = LocalVaultReader(VAULT_PATH)
        self.index = OntologyIndex(reader)

    def test_size(self):
        self.assertEqual(self.index.size, 26)

    def test_get_by_label(self):
        entry = self.index.get("Loan")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.api_name, "LLC_BI__Loan__c")
        self.assertEqual(entry.domain, "loan-origination")

    def test_get_by_api_name(self):
        entry = self.index.get("LLC_BI__Loan__c")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.label, "Loan")

    def test_get_case_insensitive(self):
        entry = self.index.get("loan")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.api_name, "LLC_BI__Loan__c")

    def test_get_not_found(self):
        self.assertIsNone(self.index.get("NonExistentEntity"))

    def test_list_entities_all(self):
        entities = self.index.list_entities()
        self.assertEqual(len(entities), 26)

    def test_list_entities_domain(self):
        entities = self.index.list_entities(domain="loan-origination")
        self.assertGreater(len(entities), 3)
        for e in entities:
            self.assertEqual(e.domain, "loan-origination")

    def test_list_domains(self):
        domains = self.index.list_domains()
        self.assertIn("loan-origination", domains)
        self.assertIn("relationship-management", domains)
        self.assertIn("collateral-management", domains)


@unittest.skipUnless(_has_vault(), "Generated vault not found at output/vault")
class TestOntologySearch(unittest.TestCase):
    def setUp(self):
        reader = LocalVaultReader(VAULT_PATH)
        index = OntologyIndex(reader)
        self.search = OntologySearch(reader, index)

    def test_get_entity_loan(self):
        entity = self.search.get_entity("Loan")
        self.assertIsNotNone(entity)
        self.assertEqual(entity.api_name, "LLC_BI__Loan__c")
        self.assertEqual(entity.domain, "loan-origination")
        self.assertEqual(entity.source_provider, "salesforce-api")
        self.assertGreater(len(entity.parents), 10)
        self.assertGreater(len(entity.children), 5)
        self.assertEqual(entity.field_count, 460)

    def test_get_entity_account(self):
        entity = self.search.get_entity("Account")
        self.assertIsNotNone(entity)
        self.assertEqual(entity.api_name, "Account")
        self.assertEqual(entity.namespace, "standard")

    def test_get_entity_not_found(self):
        self.assertIsNone(self.search.get_entity("FakeEntity"))

    def test_get_relationships_parents(self):
        parents = self.search.get_relationships("Loan", direction="parent")
        self.assertGreater(len(parents), 10)
        account_rel = next((r for r in parents if r.entity == "Account"), None)
        self.assertIsNotNone(account_rel)
        self.assertEqual(account_rel.field_api_name, "LLC_BI__Account__c")
        self.assertEqual(account_rel.relationship_type, "Lookup")

    def test_get_relationships_children(self):
        children = self.search.get_relationships("Loan", direction="child")
        self.assertGreater(len(children), 5)

    def test_list_domain(self):
        entities = self.search.list_domain("loan-origination")
        labels = [e.label for e in entities]
        self.assertIn("Loan", labels)
        self.assertIn("Application", labels)
        self.assertIn("Product", labels)

    def test_traverse_depth_0(self):
        nodes = self.search.traverse("Loan", depth=0)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].entity, "Loan")
        self.assertEqual(nodes[0].depth, 0)

    def test_traverse_depth_1(self):
        nodes = self.search.traverse("Loan", depth=1)
        self.assertGreater(len(nodes), 10)
        depths = {n.depth for n in nodes}
        self.assertIn(0, depths)
        self.assertIn(1, depths)

    def test_traverse_no_duplicates(self):
        nodes = self.search.traverse("Loan", depth=2)
        entities = [n.entity for n in nodes]
        self.assertEqual(len(entities), len(set(e.lower() for e in entities)))

    def test_description_extraction(self):
        entity = self.search.get_entity("Loan")
        self.assertIn("Loan Object", entity.description)

    def test_get_relationships_filter_lookup(self):
        rels = self.search.get_relationships("Loan", direction="child", rel_type="Lookup")
        self.assertGreater(len(rels), 0)
        for r in rels:
            self.assertEqual(r.relationship_type, "Lookup")

    def test_get_relationships_filter_master_detail(self):
        rels = self.search.get_relationships("Loan", direction="child", rel_type="MasterDetail")
        self.assertGreater(len(rels), 0)
        for r in rels:
            self.assertEqual(r.relationship_type, "MasterDetail")

    def test_get_relationships_filter_case_insensitive(self):
        rels = self.search.get_relationships("Loan", rel_type="lookup")
        self.assertGreater(len(rels), 0)

    def test_search_fields_by_name(self):
        results = self.search.search_fields("Amount")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertTrue(
                "amount" in r.field_name.lower() or "amount" in r.field_label.lower()
            )

    def test_search_fields_by_type(self):
        results = self.search.search_fields("", field_type="Currency")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r.field_type, "Currency")

    def test_search_fields_by_domain(self):
        results = self.search.search_fields("", field_type="Currency", domain="loan-origination")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r.domain, "loan-origination")

    def test_search_fields_no_match(self):
        results = self.search.search_fields("zzz_nonexistent_zzz")
        self.assertEqual(len(results), 0)


@unittest.skipUnless(_has_vault(), "Generated vault not found at output/vault")
class TestSourceResolver(unittest.TestCase):
    def setUp(self):
        reader = LocalVaultReader(VAULT_PATH)
        index = OntologyIndex(reader)
        search = OntologySearch(reader, index)
        self.resolver = SourceResolver(search)

    def test_resolve_loan(self):
        mapping = self.resolver.resolve("Loan")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.provider, "salesforce-api")
        self.assertEqual(mapping.freshness_sla, "realtime")
        self.assertEqual(mapping.api_name, "LLC_BI__Loan__c")

    def test_resolve_not_found(self):
        self.assertIsNone(self.resolver.resolve("NonExistent"))

    def test_resolve_chain(self):
        chain = self.resolver.resolve_chain("Loan", depth=1)
        self.assertGreater(len(chain), 5)
        api_names = [m.api_name for m in chain]
        self.assertIn("LLC_BI__Loan__c", api_names)


class TestFrontmatter(unittest.TestCase):
    def test_parse_simple(self):
        text = "---\napi_name: Test\nlabel: Test Label\ntier: 1\n---\n# Body"
        fm, body = parse_frontmatter(text)
        self.assertEqual(fm["api_name"], "Test")
        self.assertEqual(fm["label"], "Test Label")
        self.assertEqual(fm["tier"], 1)
        self.assertEqual(body, "# Body")

    def test_parse_inline_list(self):
        text = "---\nrecord_types: [A, B, C]\n---\nBody"
        fm, _ = parse_frontmatter(text)
        self.assertEqual(fm["record_types"], ["A", "B", "C"])

    def test_parse_no_frontmatter(self):
        text = "# Just a heading\nSome text"
        fm, body = parse_frontmatter(text)
        self.assertEqual(fm, {})
        self.assertEqual(body, text)

    def test_parse_boolean(self):
        text = "---\nenabled: true\ndisabled: false\n---\n"
        fm, _ = parse_frontmatter(text)
        self.assertTrue(fm["enabled"])
        self.assertFalse(fm["disabled"])


if __name__ == "__main__":
    unittest.main()
