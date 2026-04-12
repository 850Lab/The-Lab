"""Thin Law Intelligence V1 — corpus load, resolution, attachment shape."""

from __future__ import annotations

import copy

import pytest

from services.law_bank.load_corpus import compute_content_hash, load_published_units
from services.law_bank.resolve import resolve_law_units, unit_matches_context
from services.law_bank.schema import law_unit_ref_from_unit


@pytest.fixture(autouse=True)
def _clear_corpus_cache():
    load_published_units.cache_clear()
    yield
    load_published_units.cache_clear()


def test_corpus_loads_seven_published_units():
    units = load_published_units()
    assert len(units) == 7
    ids = sorted(u["unitId"] for u in units)
    assert ids == [
        "law_cfpb_complaint_channel_v1",
        "law_fcra_cra_reinvestigation_v1",
        "law_fcra_furnisher_accuracy_duties_v1",
        "law_fcra_identity_blocking_v1",
        "law_fcra_maximum_possible_accuracy_v1",
        "law_fdcpa_collection_misrepresentation_signal_v1",
        "law_fdcpa_validation_right_v1",
    ]


def test_content_hash_round_trip():
    units = load_published_units()
    u = copy.deepcopy(units[0])
    assert compute_content_hash(u) == u["contentHash"]


def test_resolve_stable_ordering_and_refs_shape():
    ctx = {
        "schemaVersion": "law_resolution_context_v1",
        "disputeRound": 1,
        "authoritativeStepId": "select_disputes",
        "hasBureauTarget": True,
        "hasFurnisherTarget": True,
        "identityContext": False,
        "escalationEligible": False,
        "hasCollectionAccountSignals": False,
        "hasInquirySignals": False,
        "subjectMatterTagsPresent": ["accuracy", "investigation"],
        "outcomePatternFlags": {
            "op_dispute_round_active": True,
            "op_eligible_pool_non_empty": True,
        },
    }
    refs = resolve_law_units(ctx)
    ids = [r["unitId"] for r in refs]
    assert ids == sorted(ids)
    assert "law_fcra_cra_reinvestigation_v1" in ids
    assert "law_fcra_maximum_possible_accuracy_v1" in ids
    assert "law_fcra_furnisher_accuracy_duties_v1" in ids
    for r in refs:
        assert set(r.keys()) == {
            "unitId",
            "version",
            "title",
            "summary",
            "leverageImpact",
            "leverageType",
            "enforcementShape",
            "primaryCitations",
        }


def test_law_unit_ref_excludes_internal_fields():
    units = load_published_units()
    ref = law_unit_ref_from_unit(units[0])
    assert "triggerConditions" not in ref
    assert "reviewedBy" not in ref
    assert "applicabilityNotes" not in ref


def test_cfpb_unit_requires_flag_and_escalation():
    u = next(
        x
        for x in load_published_units()
        if x["unitId"] == "law_cfpb_complaint_channel_v1"
    )
    assert not unit_matches_context(
        u,
        {
            "escalationEligible": True,
            "outcomePatternFlags": {"op_cfpb_action_available": False},
        },
    )
    assert unit_matches_context(
        u,
        {
            "escalationEligible": True,
            "outcomePatternFlags": {"op_cfpb_action_available": True},
        },
    )


def test_missing_required_bool_context_field_fails_match():
    u = next(
        x
        for x in load_published_units()
        if x["unitId"] == "law_fcra_identity_blocking_v1"
    )
    assert not unit_matches_context(u, {})
    assert not unit_matches_context(u, {"identityContext": False})
    assert unit_matches_context(u, {"identityContext": True})
