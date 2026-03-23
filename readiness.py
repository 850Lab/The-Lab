"""
readiness.py | 850 Lab Parser Machine
Immutable Contracts - Deterministic Readiness Logic

Implements Node 1 (Reason Codes), Node 3 (Canonical Inputs), and deterministic flow.
All functions are deterministic: same inputs always produce same outputs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from constants import (
    BLOCKER_REASON_CODES,
    INCLUDE_REASON_CODES,
    INCLUDE_PRIORITY_ORDER,
    INCLUDE_MAPPING,
    BLOCKER_MAPPING,
    CAPACITY_LIMIT_V1,
)
from evidence_chain import build_evidence_chain, validate_evidence_chain
from truth_posture import validate_letter_language_tier


@dataclass
class Decision:
    claim_id: str
    include_reason_code: Optional[str] = None
    blocker_reason_code: Optional[str] = None
    ui_label: str = ""
    user_action: str = ""
    letter_language_tier: Optional[str] = None
    posture: str = "NONE"


@dataclass
class LetterCandidate:
    letter_key: Tuple[str, str, str] = ("", "", "")
    claims: List[str] = field(default_factory=list)
    include_reasons: List[str] = field(default_factory=list)
    rank_key: Tuple = field(default_factory=tuple)


def _map_claim_type_to_canonical(claim_type: str) -> str:
    mapping = {
        "account": "account",
        "inquiry": "inquiry",
        "public_record": "public_record",
        "identity": "identity",
        "negative_item": "negative_item",
        "identity_verification": "identity",
        "account_ownership": "account",
        "duplicate_account": "account",
        "negative_impact": "negative_item",
        "accuracy_verification": "account",
        "unverifiable_information": "account",
    }
    return mapping.get(claim_type, "account")


def _determine_posture(claim: Dict[str, Any]) -> str:
    last_action = claim.get("last_action_type", "NONE")
    escalation_allowed = claim.get("escalation_allowed", False)
    claim_type = _map_claim_type_to_canonical(claim.get("claim_type", "account"))

    if claim_type == "identity":
        return "IDENTITY"

    if last_action in ("VERIFY", "DIRECT") and escalation_allowed:
        response_received = claim.get("response_received", False)
        response_resolved = claim.get("response_resolved_issue", False)
        if response_received and not response_resolved:
            return "ESCALATE"

    if last_action == "NONE":
        return "VERIFY"

    return "DIRECT"


def _override_tier_for_identity(claim_type: str, tier: str) -> str:
    canonical = _map_claim_type_to_canonical(claim_type)
    if canonical == "identity":
        return "TIER_IDENTITY"
    return tier


def evaluate_claim_readiness(claim: Dict[str, Any], canonical_inputs: Dict[str, Any]) -> Decision:
    claim_id = claim.get("claim_id", "")
    claim_type = claim.get("claim_type", "account")

    required_fields = ["claim_id", "claim_type", "bureau"]
    for f in required_fields:
        if not claim.get(f):
            mapping = BLOCKER_MAPPING["MISSING_REQUIRED_FIELDS"]
            return Decision(
                claim_id=claim_id,
                blocker_reason_code="MISSING_REQUIRED_FIELDS",
                ui_label=mapping["ui_label"],
                user_action=mapping["user_action"],
                posture="NONE",
            )

    identity_confirmed = canonical_inputs.get("identity_confirmed", False)
    canonical_type = _map_claim_type_to_canonical(claim_type)
    if canonical_type == "identity" and not identity_confirmed:
        mapping = BLOCKER_MAPPING["IDENTITY_NOT_CONFIRMED"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="IDENTITY_NOT_CONFIRMED",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    requires_confirmation = claim.get("requires_user_confirmation", False)
    user_confirmation_complete = claim.get("user_confirmation_complete", False)
    if requires_confirmation and not user_confirmation_complete:
        mapping = BLOCKER_MAPPING["NEEDS_USER_CONFIRMATION"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="NEEDS_USER_CONFIRMATION",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    action_possible = claim.get("action_possible", True)
    if not action_possible:
        mapping = BLOCKER_MAPPING["NO_ACTIONABLE_BASIS"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="NO_ACTIONABLE_BASIS",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    deadline_at = claim.get("deadline_at")
    response_received = claim.get("response_received", False)
    if deadline_at and not response_received:
        mapping = BLOCKER_MAPPING["WAITING_FOR_RESPONSE"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="WAITING_FOR_RESPONSE",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    action_suboptimal = claim.get("action_now_is_suboptimal", False)
    if action_suboptimal:
        mapping = BLOCKER_MAPPING["POSITIONED_TIMING"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="POSITIONED_TIMING",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    conflicting_data = claim.get("conflicting_data_requires_review", False)
    if conflicting_data:
        mapping = BLOCKER_MAPPING["CONFLICTING_DATA_REQUIRES_REVIEW"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="CONFLICTING_DATA_REQUIRES_REVIEW",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    duplicate_or_superseded = claim.get("duplicate_or_superseded", False)
    if duplicate_or_superseded:
        mapping = BLOCKER_MAPPING["DUPLICATE_OR_SUPERSEDED"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="DUPLICATE_OR_SUPERSEDED",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    out_of_scope = claim.get("out_of_scope_v1", False)
    if out_of_scope:
        mapping = BLOCKER_MAPPING["OUT_OF_SCOPE_V1"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="OUT_OF_SCOPE_V1",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    inconsistencies = claim.get("inconsistencies_present", False)
    confidence = claim.get("confidence_level", "low")
    actionable_basis = claim.get("actionable_basis_present", False)
    ownership = claim.get("ownership_confirmed", "unknown")
    user_assertions = claim.get("user_assertion_flags", [])
    last_action = claim.get("last_action_type", "NONE")
    escalation_allowed = claim.get("escalation_allowed", False)
    verification_allowed = claim.get("verification_allowed", True)

    posture = _determine_posture(claim)

    if last_action != "NONE" and escalation_allowed:
        resp_received = claim.get("response_received", False)
        resp_resolved = claim.get("response_resolved_issue", False)
        if resp_received and not resp_resolved:
            include_code = "POST_VERIFICATION_ESCALATION"
            mapping = INCLUDE_MAPPING[include_code]
            tier = _override_tier_for_identity(claim_type, mapping["letter_language_tier"])
            return Decision(
                claim_id=claim_id,
                include_reason_code=include_code,
                ui_label=mapping["ui_label"],
                user_action=mapping["user_action"],
                letter_language_tier=tier,
                posture=posture,
            )

    if canonical_type == "identity" and identity_confirmed:
        if user_assertions and "INCORRECT_IDENTITY" in user_assertions:
            include_code = "IDENTITY_CORRECTION_REQUEST"
            mapping = INCLUDE_MAPPING[include_code]
            return Decision(
                claim_id=claim_id,
                include_reason_code=include_code,
                ui_label=mapping["ui_label"],
                user_action=mapping["user_action"],
                letter_language_tier="TIER_IDENTITY",
                posture="IDENTITY",
            )

    if confidence == "high" and actionable_basis:
        if user_confirmation_complete and user_assertions:
            include_code = "USER_CONFIRMED_FACT"
            mapping = INCLUDE_MAPPING[include_code]
            tier = _override_tier_for_identity(claim_type, mapping["letter_language_tier"])
            return Decision(
                claim_id=claim_id,
                include_reason_code=include_code,
                ui_label=mapping["ui_label"],
                user_action=mapping["user_action"],
                letter_language_tier=tier,
                posture=posture,
            )

        include_code = "HIGH_CONFIDENCE_ACCURACY"
        mapping = INCLUDE_MAPPING[include_code]
        tier = _override_tier_for_identity(claim_type, mapping["letter_language_tier"])
        return Decision(
            claim_id=claim_id,
            include_reason_code=include_code,
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            letter_language_tier=tier,
            posture=posture,
        )

    if inconsistencies and verification_allowed:
        include_code = "INCONSISTENCY_VERIFICATION"
        mapping = INCLUDE_MAPPING[include_code]
        tier = _override_tier_for_identity(claim_type, mapping["letter_language_tier"])
        return Decision(
            claim_id=claim_id,
            include_reason_code=include_code,
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            letter_language_tier=tier,
            posture=posture,
        )

    if user_confirmation_complete and user_assertions:
        include_code = "USER_CONFIRMED_FACT"
        mapping = INCLUDE_MAPPING[include_code]
        tier = _override_tier_for_identity(claim_type, mapping["letter_language_tier"])
        return Decision(
            claim_id=claim_id,
            include_reason_code=include_code,
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            letter_language_tier=tier,
            posture=posture,
        )

    if actionable_basis and ownership != False:
        if not verification_allowed:
            include_code = "UNVERIFIABLE_RECORD_REQUEST"
            mapping = INCLUDE_MAPPING[include_code]
            tier = _override_tier_for_identity(claim_type, mapping["letter_language_tier"])
            return Decision(
                claim_id=claim_id,
                include_reason_code=include_code,
                ui_label=mapping["ui_label"],
                user_action=mapping["user_action"],
                letter_language_tier=tier,
                posture=posture,
            )

    if confidence == "low" and not verification_allowed:
        mapping = BLOCKER_MAPPING["LOW_CONFIDENCE_NO_VERIFY_PATH"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="LOW_CONFIDENCE_NO_VERIFY_PATH",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    if not actionable_basis:
        mapping = BLOCKER_MAPPING["NO_ACTIONABLE_BASIS"]
        return Decision(
            claim_id=claim_id,
            blocker_reason_code="NO_ACTIONABLE_BASIS",
            ui_label=mapping["ui_label"],
            user_action=mapping["user_action"],
            posture="NONE",
        )

    mapping = BLOCKER_MAPPING["LOW_CONFIDENCE_NO_VERIFY_PATH"]
    return Decision(
        claim_id=claim_id,
        blocker_reason_code="LOW_CONFIDENCE_NO_VERIFY_PATH",
        ui_label=mapping["ui_label"],
        user_action=mapping["user_action"],
        posture="NONE",
    )


def _compute_evidence_strength(tiers: List[str]) -> int:
    tier_weights = {"TIER_A": 4, "TIER_B": 3, "TIER_C": 2, "TIER_D": 1}
    return sum(tier_weights.get(t, 0) for t in tiers)


def group_into_letters(
    decisions: List[Decision],
    claims: List[Dict[str, Any]],
) -> List[LetterCandidate]:
    claim_map = {c.get("claim_id", ""): c for c in claims}
    letter_groups: Dict[Tuple[str, str, str], List[Tuple[str, str]]] = {}

    for decision in decisions:
        if decision.include_reason_code is None:
            continue

        claim = claim_map.get(decision.claim_id, {})
        bureau = claim.get("bureau", "").upper()
        if bureau not in ("EQ", "EX", "TU"):
            bureau_lower = claim.get("bureau", "").lower()
            bureau_map = {
                "equifax": "EQ",
                "experian": "EX",
                "transunion": "TU",
                "eq": "EQ",
                "ex": "EX",
                "tu": "TU",
            }
            bureau = bureau_map.get(bureau_lower, bureau.upper()[:2])

        last_action = claim.get("last_action_type", "NONE")
        escalation_allowed = claim.get("escalation_allowed", False)
        resp_received = claim.get("response_received", False)
        resp_resolved = claim.get("response_resolved_issue", False)

        if (
            last_action != "NONE"
            and escalation_allowed
            and resp_received
            and not resp_resolved
        ):
            target_type = "FURNISHER"
        else:
            target_type = "BUREAU"

        fields = claim.get("fields", {})
        creditor_raw = (
            fields.get("normalized_creditor_name", "")
            or fields.get("creditor", "")
            or fields.get("account_name", "")
            or ""
        )
        creditor_norm = creditor_raw.upper().strip()

        letter_key = (target_type, creditor_norm, bureau)

        if letter_key not in letter_groups:
            letter_groups[letter_key] = []
        letter_groups[letter_key].append(
            (decision.claim_id, decision.include_reason_code)
        )

    candidates = []
    for lk, claim_reasons in sorted(letter_groups.items()):
        claim_ids = sorted([cr[0] for cr in claim_reasons])
        reasons = list(dict.fromkeys(cr[1] for cr in sorted(claim_reasons)))

        candidates.append(
            LetterCandidate(
                letter_key=lk,
                claims=claim_ids,
                include_reasons=reasons,
                rank_key=(),
            )
        )

    return candidates


def _best_include_priority(reasons: List[str]) -> int:
    best = len(INCLUDE_PRIORITY_ORDER)
    for reason in reasons:
        if reason in INCLUDE_PRIORITY_ORDER:
            idx = INCLUDE_PRIORITY_ORDER.index(reason)
            if idx < best:
                best = idx
    return best


def rank_letters(
    letter_candidates: List[LetterCandidate],
    validated_evidence: Optional[Dict[str, List[str]]] = None,
) -> List[LetterCandidate]:
    for candidate in letter_candidates:
        priority = _best_include_priority(candidate.include_reasons)

        evidence_strength = 0
        if validated_evidence:
            for cid in candidate.claims:
                tiers = validated_evidence.get(cid, [])
                evidence_strength = max(evidence_strength, _compute_evidence_strength(tiers))
        neg_evidence = -evidence_strength

        lexical = candidate.letter_key
        candidate.rank_key = (priority, neg_evidence, lexical)

    return sorted(letter_candidates, key=lambda c: c.rank_key)


def apply_capacity(
    letter_candidates: List[LetterCandidate],
    capacity_limit: int = CAPACITY_LIMIT_V1,
    validated_evidence: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[LetterCandidate]]:
    ranked = rank_letters(letter_candidates, validated_evidence=validated_evidence)
    selected = ranked[:capacity_limit]
    overflow = ranked[capacity_limit:]
    return {"selected": selected, "overflow": overflow}


def build_blocker_rollup(
    decisions: List[Decision],
) -> List[Dict[str, Any]]:
    rollup: Dict[str, Dict[str, Any]] = {}

    for decision in decisions:
        code = decision.blocker_reason_code
        if code is None:
            continue
        if code not in rollup:
            rollup[code] = {
                "code": code,
                "label": decision.ui_label,
                "action": decision.user_action,
                "count": 0,
            }
        rollup[code]["count"] += 1

    sorted_rollup = sorted(rollup.values(), key=lambda r: -r["count"])
    return sorted_rollup
