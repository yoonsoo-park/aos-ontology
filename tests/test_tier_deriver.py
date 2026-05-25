"""Tests for tier_deriver: Pass 1 filter + Pass 2 scoring."""

from __future__ import annotations

import pytest

from scripts.ontology.models import SFObject, SFRelationship
from scripts.ontology.tier_deriver import (
    INFRA_EXCLUDE,
    apply_overrides,
    compute_recall,
    derive_tiers,
)


def _mk(
    name: str,
    namespace: str = "",
    in_rels: int = 0,
    out_rels: int = 0,
    record_types: int = 0,
) -> SFObject:
    obj = SFObject(api_name=name, label=name, namespace=namespace)
    for i in range(out_rels):
        obj.relationships.append(
            SFRelationship(
                field_api_name=f"f{i}",
                source_object=name,
                target_object=f"Tgt{i}",
                relationship_type="Lookup",
                relationship_name=f"r{i}",
                relationship_label=f"R{i}",
            )
        )
    for i in range(in_rels):
        obj.incoming_relationships.append(
            SFRelationship(
                field_api_name=f"in{i}",
                source_object=f"Src{i}",
                target_object=name,
                relationship_type="Lookup",
                relationship_name=f"in{i}",
                relationship_label=f"In{i}",
            )
        )
    obj.record_types = [f"rt{i}" for i in range(record_types)]
    return obj


def test_infra_excluded():
    objs = {
        "User": _mk("User", in_rels=999),
        "Profile": _mk("Profile", in_rels=999),
        "RecordType": _mk("RecordType", in_rels=999),
        "Organization": _mk("Organization", in_rels=999),
    }
    result = derive_tiers(objs, manifest_objects=set())
    assert result.tier_1 == []
    assert result.tier_2 == []
    assert all(s.api_name not in INFRA_EXCLUDE for s in result.scored)


def test_llc_bi_always_included():
    objs = {"LLC_BI__Loan__c": _mk("LLC_BI__Loan__c", namespace="LLC_BI", in_rels=0)}
    result = derive_tiers(objs, manifest_objects=set())
    assert "LLC_BI__Loan__c" in result.all_tiered


def test_nsba_always_included():
    objs = {"nSBA__Form__c": _mk("nSBA__Form__c", namespace="nSBA", in_rels=0)}
    result = derive_tiers(objs, manifest_objects=set())
    assert "nSBA__Form__c" in result.all_tiered


def test_nforce_excluded():
    """nFORCE: 0/69 in current TIERS → fully excluded by Pass 1."""
    objs = {
        "nFORCE__Screen__c": _mk(
            "nFORCE__Screen__c", namespace="nFORCE", in_rels=200, record_types=5
        )
    }
    result = derive_tiers(objs, manifest_objects={"nFORCE__Screen__c"})
    assert result.tier_1 == []
    assert result.tier_2 == []


def test_standard_requires_manifest_and_degree():
    objs = {
        "Account": _mk("Account", namespace="", in_rels=20),
        "Contact": _mk("Contact", namespace="", in_rels=2),  # below threshold
        "Lead": _mk("Lead", namespace="", in_rels=10),  # not in manifest
    }
    result = derive_tiers(objs, manifest_objects={"Account"})
    included = {s.api_name for s in result.scored}
    assert "Account" in included
    assert "Contact" not in included
    assert "Lead" not in included


def test_score_ordering_and_sizes():
    objs = {}
    # 30 LLC_BI objects with varying in_degree
    for i in range(30):
        name = f"LLC_BI__O{i:02d}__c"
        objs[name] = _mk(name, namespace="LLC_BI", in_rels=i)
    result = derive_tiers(objs, manifest_objects=set(), tier_1_size=5, tier_2_size=10)
    assert len(result.tier_1) == 5
    assert len(result.tier_2) == 10
    # highest in_degree first
    assert result.tier_1[0] == "LLC_BI__O29__c"


def test_record_types_and_manifest_boost():
    objs = {
        "LLC_BI__A__c": _mk("LLC_BI__A__c", namespace="LLC_BI", in_rels=10),
        "LLC_BI__B__c": _mk(
            "LLC_BI__B__c", namespace="LLC_BI", in_rels=10, record_types=3
        ),
        "LLC_BI__C__c": _mk("LLC_BI__C__c", namespace="LLC_BI", in_rels=10),
    }
    result = derive_tiers(
        objs, manifest_objects={"LLC_BI__C__c"}, tier_1_size=3, tier_2_size=0
    )
    # C: in_manifest (+30), B: record_types (+10), A: nothing
    assert result.tier_1[0] == "LLC_BI__C__c"
    assert result.tier_1[1] == "LLC_BI__B__c"
    assert result.tier_1[2] == "LLC_BI__A__c"


def test_manifest_case_insensitive():
    """manifest may have canonical-first-wins casing different from metadata."""
    objs = {
        "LLC_BI__Application__c": _mk(
            "LLC_BI__Application__c", namespace="LLC_BI", in_rels=5
        )
    }
    # manifest stored uppercase __C variant
    result = derive_tiers(objs, manifest_objects={"LLC_BI__Application__C"})
    scored = {s.api_name: s for s in result.scored}
    assert scored["LLC_BI__Application__c"].in_manifest is True


def test_deterministic_tiebreak():
    objs = {
        "LLC_BI__B__c": _mk("LLC_BI__B__c", namespace="LLC_BI", in_rels=10),
        "LLC_BI__A__c": _mk("LLC_BI__A__c", namespace="LLC_BI", in_rels=10),
        "LLC_BI__C__c": _mk("LLC_BI__C__c", namespace="LLC_BI", in_rels=10),
    }
    r1 = derive_tiers(objs, set(), tier_1_size=3, tier_2_size=0)
    r2 = derive_tiers(objs, set(), tier_1_size=3, tier_2_size=0)
    assert r1.tier_1 == r2.tier_1 == ["LLC_BI__A__c", "LLC_BI__B__c", "LLC_BI__C__c"]


def test_compute_recall():
    derived = ["A", "B", "c"]
    baseline = ["A", "B", "C", "D"]
    recall, hits, misses = compute_recall(derived, baseline)
    assert hits == ["A", "B", "C"]
    assert misses == ["D"]
    assert recall == pytest.approx(0.75)


# --- apply_overrides ---------------------------------------------------------


def test_apply_overrides_force_t1_promotes_to_tier1():
    objs = {f"O{i}": _mk(f"O{i}", "LLC_BI", in_rels=10 - i) for i in range(10)}
    auto = derive_tiers(objs, manifest_objects=set())
    result = apply_overrides(auto, force_t1=["O9"], tier_1_size=3, tier_2_size=3)
    assert "O9" in result.tier_1
    assert len(result.tier_1) == 3


def test_apply_overrides_force_t2_promotes_to_tier2():
    objs = {f"O{i}": _mk(f"O{i}", "LLC_BI", in_rels=10 - i) for i in range(10)}
    auto = derive_tiers(objs, manifest_objects=set())
    result = apply_overrides(auto, force_t2=["O9"], tier_1_size=3, tier_2_size=3)
    assert "O9" in result.tier_2
    assert "O9" not in result.tier_1


def test_apply_overrides_force_exclude_removes():
    objs = {f"O{i}": _mk(f"O{i}", "LLC_BI", in_rels=10 - i) for i in range(10)}
    auto = derive_tiers(objs, manifest_objects=set())
    result = apply_overrides(auto, force_exclude=["O0"], tier_1_size=3, tier_2_size=3)
    assert "O0" not in result.tier_1
    assert "O0" not in result.tier_2
    assert "O0" not in result.tier_3


def test_apply_overrides_t1_t2_dedupe():
    """If a name appears in both force_t1 and force_t2, T1 wins."""
    objs = {f"O{i}": _mk(f"O{i}", "LLC_BI", in_rels=10 - i) for i in range(10)}
    auto = derive_tiers(objs, manifest_objects=set())
    result = apply_overrides(
        auto, force_t1=["O5"], force_t2=["O5"], tier_1_size=3, tier_2_size=3
    )
    assert "O5" in result.tier_1
    assert "O5" not in result.tier_2


def test_apply_overrides_case_insensitive_exclude():
    objs = {"LLC_BI__Foo__c": _mk("LLC_BI__Foo__c", "LLC_BI", in_rels=10)}
    auto = derive_tiers(objs, manifest_objects=set())
    result = apply_overrides(auto, force_exclude=["llc_bi__foo__c"])
    assert "LLC_BI__Foo__c" not in result.tier_1
