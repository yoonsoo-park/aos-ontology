"""Unit tests for scripts.ontology.manifest_loader.

Tests cover:
  - Topological sort (DFS) correctness and cycle detection
  - Recursion / nested MoM handling
  - objectName extraction from sfRecordData and sfSeedData
  - Case-insensitive diff against a TIER list
  - End-to-end load against a tmp-path mini fixture

These tests are pure stdlib (no Demo-Master required). A separate manual
script can verify against the real Demo-Master clone.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ontology.manifest_loader import (
    ManifestCycleError,
    ManifestDepthError,
    diff_against_tier,
    load_manifest_dag,
    _topo_sort,
)


def _write(repo: Path, rel: str, payload: dict) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload))


# ---------------------------------------------------------------------------
# _topo_sort
# ---------------------------------------------------------------------------


def test_topo_sort_simple_chain():
    entries = [
        {"alias": "C", "dependencies": ["B"]},
        {"alias": "A", "dependencies": []},
        {"alias": "B", "dependencies": ["A"]},
    ]
    ordered = [e["alias"] for e in _topo_sort(entries)]
    assert ordered == ["A", "B", "C"]


def test_topo_sort_diamond():
    entries = [
        {"alias": "D", "dependencies": ["B", "C"]},
        {"alias": "B", "dependencies": ["A"]},
        {"alias": "C", "dependencies": ["A"]},
        {"alias": "A", "dependencies": []},
    ]
    ordered = [e["alias"] for e in _topo_sort(entries)]
    assert ordered.index("A") < ordered.index("B")
    assert ordered.index("A") < ordered.index("C")
    assert ordered.index("B") < ordered.index("D")
    assert ordered.index("C") < ordered.index("D")


def test_topo_sort_cycle_raises():
    entries = [
        {"alias": "A", "dependencies": ["B"]},
        {"alias": "B", "dependencies": ["A"]},
    ]
    with pytest.raises(ManifestCycleError):
        _topo_sort(entries)


def test_topo_sort_unknown_dependency_raises():
    entries = [{"alias": "A", "dependencies": ["B"]}]
    with pytest.raises(ValueError, match="Dependency not found"):
        _topo_sort(entries)


# ---------------------------------------------------------------------------
# load_manifest_dag — flat MoM
# ---------------------------------------------------------------------------


def test_flat_mom_extracts_objects(tmp_path: Path):
    _write(
        tmp_path,
        "mom.json",
        {
            "manifests": [
                {"alias": "BASE", "path": "configs/base.json", "dependencies": []},
                {
                    "alias": "DATA",
                    "path": "configs/data.json",
                    "dependencies": ["BASE"],
                },
            ]
        },
    )
    _write(
        tmp_path,
        "configs/base.json",
        {
            "configuration": {
                "sfRecordData": {
                    "recordGroups": {
                        "g1": {"records": [{"objectName": "Account"}]}
                    }
                }
            }
        },
    )
    _write(
        tmp_path,
        "configs/data.json",
        {
            "configuration": {
                "sfRecordData": {
                    "recordGroups": {
                        "g1": {
                            "records": [
                                {"objectName": "LLC_BI__Loan__c"},
                                {"objectName": "Contact"},
                            ]
                        }
                    }
                },
                "sfSeedData": {
                    "recordGroups": {
                        "g2": {"records": [{"objectName": "LLC_BI__Branch__c"}]}
                    }
                },
            }
        },
    )

    result = load_manifest_dag(tmp_path, mom_path="mom.json")

    assert result.union_objects == {
        "Account",
        "LLC_BI__Loan__c",
        "Contact",
        "LLC_BI__Branch__c",
    }
    aliases = [n.alias for n in result.ordered_nodes if n.is_mom is False]
    # BASE must come before DATA (topo order)
    assert aliases.index("BASE") < aliases.index("DATA")

    assert result.object_to_manifests["Account"] == frozenset({"BASE"})
    assert result.object_to_manifests["LLC_BI__Loan__c"] == frozenset({"DATA"})


# ---------------------------------------------------------------------------
# Nested MoM
# ---------------------------------------------------------------------------


def test_nested_mom(tmp_path: Path):
    _write(
        tmp_path,
        "root.json",
        {
            "manifests": [
                {"alias": "OUTER", "path": "outer.json", "dependencies": []},
            ]
        },
    )
    _write(
        tmp_path,
        "outer.json",
        {
            "manifests": [
                {"alias": "INNER", "path": "configs/inner.json", "dependencies": []},
            ]
        },
    )
    _write(
        tmp_path,
        "configs/inner.json",
        {
            "configuration": {
                "sfRecordData": {
                    "recordGroups": {
                        "g": {"records": [{"objectName": "LLC_BI__Application__c"}]}
                    }
                }
            }
        },
    )

    result = load_manifest_dag(tmp_path, mom_path="root.json")
    assert "LLC_BI__Application__c" in result.union_objects
    inner = next(n for n in result.ordered_nodes if n.alias == "INNER")
    assert inner.depth == 2
    assert inner.parent_alias == "OUTER"


def test_max_depth_exceeded(tmp_path: Path):
    # Build 12 nested MoMs all pointing inward
    for i in range(12):
        next_path = f"m{i+1}.json" if i < 11 else None
        payload = {}
        if next_path:
            payload["manifests"] = [
                {"alias": f"L{i+1}", "path": next_path, "dependencies": []}
            ]
        else:
            payload["configuration"] = {}
        _write(tmp_path, f"m{i}.json", payload)

    with pytest.raises(ManifestDepthError):
        load_manifest_dag(tmp_path, mom_path="m0.json")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_missing_configuration_is_ok(tmp_path: Path):
    """A leaf manifest without `configuration` is valid (just contributes 0 objects)."""
    _write(
        tmp_path,
        "mom.json",
        {"manifests": [{"alias": "X", "path": "x.json", "dependencies": []}]},
    )
    _write(tmp_path, "x.json", {})  # neither manifests nor configuration
    result = load_manifest_dag(tmp_path, mom_path="mom.json")
    assert result.union_objects == frozenset()


def test_objectname_blank_or_missing_skipped(tmp_path: Path):
    _write(
        tmp_path,
        "mom.json",
        {"manifests": [{"alias": "X", "path": "x.json", "dependencies": []}]},
    )
    _write(
        tmp_path,
        "x.json",
        {
            "configuration": {
                "sfRecordData": {
                    "recordGroups": {
                        "g": {
                            "records": [
                                {"objectName": ""},
                                {"objectName": "   "},
                                {},
                                {"objectName": "Account"},
                            ]
                        }
                    }
                }
            }
        },
    )
    result = load_manifest_dag(tmp_path, mom_path="mom.json")
    assert result.union_objects == {"Account"}


def test_alias_fallback_to_filename(tmp_path: Path):
    """Entries without `alias` should fall back to the filename stem."""
    _write(
        tmp_path,
        "mom.json",
        {"manifests": [{"path": "configs/base-config.json", "dependencies": []}]},
    )
    _write(
        tmp_path,
        "configs/base-config.json",
        {
            "configuration": {
                "sfRecordData": {
                    "recordGroups": {"g": {"records": [{"objectName": "Account"}]}}
                }
            }
        },
    )
    result = load_manifest_dag(tmp_path, mom_path="mom.json")
    aliases = {n.alias for n in result.ordered_nodes if not n.is_mom}
    assert "base-config" in aliases


# ---------------------------------------------------------------------------
# diff_against_tier
# ---------------------------------------------------------------------------


def test_diff_against_tier(tmp_path: Path):
    _write(
        tmp_path,
        "mom.json",
        {"manifests": [{"alias": "X", "path": "x.json", "dependencies": []}]},
    )
    _write(
        tmp_path,
        "x.json",
        {
            "configuration": {
                "sfRecordData": {
                    "recordGroups": {
                        "g": {
                            "records": [
                                {"objectName": "LLC_BI__Application__C"},  # typo
                                {"objectName": "Account"},
                                {"objectName": "LLC_BI__Loan__c"},
                            ]
                        }
                    }
                }
            }
        },
    )
    result = load_manifest_dag(tmp_path, mom_path="mom.json")

    tier = [
        "Account",
        "LLC_BI__Loan__c",
        "LLC_BI__Application__c",  # canonical SF name
        "LLC_BI__Covenant__c",  # not present anywhere
    ]
    diff = diff_against_tier(tier, result)

    assert diff["exact"] == ["Account", "LLC_BI__Loan__c"]
    assert diff["case_mismatch"] == [
        "LLC_BI__Application__c -> LLC_BI__Application__C"
    ]
    assert diff["missing"] == ["LLC_BI__Covenant__c"]


def test_canonical_case_first_wins(tmp_path: Path):
    """When a name appears in multiple casings, first-seen wins as canonical."""
    _write(
        tmp_path,
        "mom.json",
        {
            "manifests": [
                {"alias": "A", "path": "a.json", "dependencies": []},
                {"alias": "B", "path": "b.json", "dependencies": ["A"]},
            ]
        },
    )
    _write(
        tmp_path,
        "a.json",
        {
            "configuration": {
                "sfRecordData": {
                    "recordGroups": {
                        "g": {"records": [{"objectName": "LLC_BI__Application__C"}]}
                    }
                }
            }
        },
    )
    _write(
        tmp_path,
        "b.json",
        {
            "configuration": {
                "sfRecordData": {
                    "recordGroups": {
                        "g": {"records": [{"objectName": "LLC_BI__Application__c"}]}
                    }
                }
            }
        },
    )
    result = load_manifest_dag(tmp_path, mom_path="mom.json")
    # Both casings collapse to one canonical entry (first-seen via topo order = A)
    assert len(result.union_objects) == 1
    assert "LLC_BI__Application__C" in result.union_objects
