"""Round execution metadata helpers (no DB)."""

from services.workflow.dispute_round_execution import (
    build_unresolved_items,
    item_disposition,
    normalize_bureau_item_outcome,
)


def test_normalize_bureau_item_outcome():
    assert normalize_bureau_item_outcome("DELETED") == "deleted"
    assert normalize_bureau_item_outcome("removed") == "deleted"
    assert normalize_bureau_item_outcome("verified_accurate") == "verified"
    assert normalize_bureau_item_outcome("no_response") == "no_response"


def test_item_disposition():
    assert item_disposition("deleted") == "resolved"
    assert item_disposition("verified") == "resolved"
    assert item_disposition("updated") == "unresolved"
    assert item_disposition("no_response") == "needs_escalation"


def test_build_unresolved_items():
    cum = {"a", "b", "c"}
    outcomes = {"a": "deleted", "b": "updated", "c": "no_response"}
    rows = build_unresolved_items(cum, outcomes)
    ids = {r["reviewClaimId"] for r in rows}
    assert ids == {"b", "c"}
    assert any(r.get("escalationSuggested") for r in rows if r["reviewClaimId"] == "c")
