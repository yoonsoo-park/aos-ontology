"""Tests for entity enrichment pipeline."""

from __future__ import annotations

import unittest

from scripts.ontology.models import SFField, SFObject, SFPicklistValue
from scripts.ontology.enrichers import (
    ConstraintEnricher,
    DescriptionEnricher,
    Enrichment,
    EnrichmentContext,
    PicklistSummaryEnricher,
    get_enrichers,
    run_enrichers,
)


def _make_loan_object() -> SFObject:
    return SFObject(
        api_name="LLC_BI__Loan__c",
        label="Loan",
        namespace="LLC_BI",
        description="The Loan Object stores information of the details of a Loan.",
        fields=[
            SFField(
                api_name="LLC_BI__Amount__c",
                label="Amount",
                type="Currency",
                required=True,
                description="The loan amount in USD.",
            ),
            SFField(
                api_name="LLC_BI__Stage__c",
                label="Stage",
                type="Picklist",
                required=True,
                unique=False,
                picklist_values=[
                    SFPicklistValue("Qualification", "Qualification"),
                    SFPicklistValue("Proposal", "Proposal"),
                    SFPicklistValue("Application", "Application"),
                    SFPicklistValue("Underwriting", "Underwriting"),
                ],
            ),
            SFField(
                api_name="LLC_BI__Loan_Number__c",
                label="Loan Number",
                type="Text",
                unique=True,
                external_id=True,
            ),
            SFField(
                api_name="LLC_BI__Account__c",
                label="Account",
                type="Lookup",
                reference_to="Account",
            ),
        ],
    )


def _make_empty_object() -> SFObject:
    return SFObject(
        api_name="LLC_BI__Empty__c",
        label="Empty",
        namespace="LLC_BI",
        fields=[
            SFField(api_name="Name", label="Name", type="Text"),
        ],
    )


class TestDescriptionEnricher(unittest.TestCase):
    def test_returns_description(self):
        obj = _make_loan_object()
        enricher = DescriptionEnricher()
        ctx = EnrichmentContext(all_objects={"LLC_BI__Loan__c": obj})
        results = enricher.enrich(obj, ctx)
        descs = [r for r in results if r.key == "description"]
        self.assertEqual(len(descs), 1)
        self.assertIn("Loan Object", descs[0].value)
        self.assertEqual(descs[0].source, "xml")

    def test_returns_field_descriptions(self):
        obj = _make_loan_object()
        enricher = DescriptionEnricher()
        ctx = EnrichmentContext(all_objects={"LLC_BI__Loan__c": obj})
        results = enricher.enrich(obj, ctx)
        field_descs = [r for r in results if r.key == "field_descriptions"]
        self.assertEqual(len(field_descs), 1)
        self.assertEqual(field_descs[0].value[0]["field"], "LLC_BI__Amount__c")

    def test_skips_relationship_fields(self):
        obj = _make_loan_object()
        enricher = DescriptionEnricher()
        ctx = EnrichmentContext(all_objects={"LLC_BI__Loan__c": obj})
        results = enricher.enrich(obj, ctx)
        field_descs = [r for r in results if r.key == "field_descriptions"]
        field_names = [fd["field"] for fd in field_descs[0].value]
        self.assertNotIn("LLC_BI__Account__c", field_names)

    def test_empty_object_returns_nothing(self):
        obj = _make_empty_object()
        enricher = DescriptionEnricher()
        ctx = EnrichmentContext(all_objects={"LLC_BI__Empty__c": obj})
        results = enricher.enrich(obj, ctx)
        self.assertEqual(results, [])


class TestConstraintEnricher(unittest.TestCase):
    def test_returns_constraints(self):
        obj = _make_loan_object()
        enricher = ConstraintEnricher()
        ctx = EnrichmentContext(all_objects={"LLC_BI__Loan__c": obj})
        results = enricher.enrich(obj, ctx)
        self.assertEqual(len(results), 1)
        constraints = results[0].value
        self.assertGreater(len(constraints), 0)

    def test_captures_required_field(self):
        obj = _make_loan_object()
        enricher = ConstraintEnricher()
        ctx = EnrichmentContext(all_objects={})
        results = enricher.enrich(obj, ctx)
        constraints = results[0].value
        amount = next(c for c in constraints if c["field"] == "LLC_BI__Amount__c")
        self.assertIn("required", amount["flags"])

    def test_captures_unique_and_external_id(self):
        obj = _make_loan_object()
        enricher = ConstraintEnricher()
        ctx = EnrichmentContext(all_objects={})
        results = enricher.enrich(obj, ctx)
        constraints = results[0].value
        loan_num = next(c for c in constraints if c["field"] == "LLC_BI__Loan_Number__c")
        self.assertIn("unique", loan_num["flags"])
        self.assertIn("external_id", loan_num["flags"])

    def test_skips_relationship_fields(self):
        obj = _make_loan_object()
        enricher = ConstraintEnricher()
        ctx = EnrichmentContext(all_objects={})
        results = enricher.enrich(obj, ctx)
        constraints = results[0].value
        field_names = [c["field"] for c in constraints]
        self.assertNotIn("LLC_BI__Account__c", field_names)

    def test_empty_returns_nothing(self):
        obj = _make_empty_object()
        enricher = ConstraintEnricher()
        ctx = EnrichmentContext(all_objects={})
        results = enricher.enrich(obj, ctx)
        self.assertEqual(results, [])


class TestPicklistSummaryEnricher(unittest.TestCase):
    def test_returns_picklists(self):
        obj = _make_loan_object()
        enricher = PicklistSummaryEnricher()
        ctx = EnrichmentContext(all_objects={})
        results = enricher.enrich(obj, ctx)
        self.assertEqual(len(results), 1)
        picklists = results[0].value
        self.assertEqual(len(picklists), 1)
        self.assertEqual(picklists[0]["field"], "LLC_BI__Stage__c")
        self.assertEqual(picklists[0]["value_count"], 4)
        self.assertIn("Qualification", picklists[0]["values"])

    def test_empty_returns_nothing(self):
        obj = _make_empty_object()
        enricher = PicklistSummaryEnricher()
        ctx = EnrichmentContext(all_objects={})
        results = enricher.enrich(obj, ctx)
        self.assertEqual(results, [])


class TestRegistry(unittest.TestCase):
    def test_get_enrichers_valid(self):
        enrichers = get_enrichers(["description", "constraints", "picklists"])
        self.assertEqual(len(enrichers), 3)

    def test_get_enrichers_invalid(self):
        with self.assertRaises(ValueError) as ctx:
            get_enrichers(["nonexistent"])
        self.assertIn("nonexistent", str(ctx.exception))
        self.assertIn("Available:", str(ctx.exception))


class TestRunEnrichers(unittest.TestCase):
    def test_run_all_enrichers(self):
        loan = _make_loan_object()
        empty = _make_empty_object()
        objects = {loan.api_name: loan, empty.api_name: empty}

        enrichers = get_enrichers(["description", "constraints", "picklists"])
        result = run_enrichers(objects, enrichers)

        self.assertIn("LLC_BI__Loan__c", result)
        loan_enrichments = result["LLC_BI__Loan__c"]
        self.assertIn("description", loan_enrichments)
        self.assertIn("constraints", loan_enrichments)
        self.assertIn("picklist_fields", loan_enrichments)

    def test_empty_object_excluded(self):
        empty = _make_empty_object()
        objects = {empty.api_name: empty}

        enrichers = get_enrichers(["description", "constraints", "picklists"])
        result = run_enrichers(objects, enrichers)

        self.assertNotIn("LLC_BI__Empty__c", result)


if __name__ == "__main__":
    unittest.main()
