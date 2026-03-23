"""Pure mapping from review claims to canonical dispute structures (Streamlit-free)."""

from __future__ import annotations

from typing import Any, Dict


def review_claim_to_canonical(
    rc: Any,
    user_response: str,
    bureau_key: str,
    identity_confirmed_for_bureau: bool,
) -> Dict[str, Any]:
    entities = getattr(rc, "entities", {}) or {}
    evidence = getattr(rc, "evidence_summary", None)
    review_type = getattr(rc, "review_type", None)
    confidence_summary = evidence.claim_confidence_summary if evidence else None

    review_type_to_claim_type = {
        "identity_verification": "identity",
        "account_ownership": "account",
        "duplicate_account": "account",
        "negative_impact": "negative_item",
        "accuracy_verification": "account",
        "unverifiable_information": "account",
    }
    claim_type = review_type_to_claim_type.get(
        review_type.value if review_type else "", "account"
    )

    bureau_map = {
        "equifax": "EQ",
        "experian": "EX",
        "transunion": "TU",
        "eq": "EQ",
        "ex": "EX",
        "tu": "TU",
    }
    bureau_code = bureau_map.get(bureau_key.lower(), bureau_key.upper()[:2])

    if confidence_summary:
        if confidence_summary.high > 0:
            confidence_level = "high"
        elif confidence_summary.medium > 0:
            confidence_level = "medium"
        else:
            confidence_level = "low"
    else:
        confidence_level = "low"

    user_confirmation_complete = user_response in ("inaccurate", "unsure")
    user_assertions = []
    if user_response == "inaccurate":
        if claim_type == "identity":
            user_assertions.append("INCORRECT_IDENTITY")
        elif review_type and review_type.value == "accuracy_verification":
            user_assertions.append("INCORRECT_BALANCE")
        else:
            user_assertions.append("NOT_MINE")

    fields = {}
    creditor = (
        entities.get("creditor")
        or entities.get("_extracted_creditor")
        or entities.get("account_name")
        or entities.get("furnisher")
        or entities.get("inquirer")
        or ""
    )
    if creditor:
        fields["creditor"] = creditor
        fields["normalized_creditor_name"] = creditor.upper().strip()
    account_ref = (
        entities.get("account_mask")
        or entities.get("last4")
        or entities.get("account")
        or entities.get("account_reference")
        or ""
    )
    if account_ref:
        fields["account_reference"] = account_ref
    for key in ("balance", "status", "opened_date", "inquiry_date"):
        val = entities.get(key)
        if val:
            fields[key] = val

    receipt_snippets = []
    if evidence and evidence.system_observations:
        receipt_snippets = evidence.system_observations[:3]

    cross_bureau = getattr(evidence, "cross_bureau_status", None)
    inconsistencies_present = (
        cross_bureau is not None
        and hasattr(cross_bureau, "value")
        and cross_bureau.value == "multi_bureau"
    )

    actionable_basis = user_confirmation_complete or confidence_level == "high"

    canonical = {
        "claim_id": rc.review_claim_id,
        "claim_type": claim_type,
        "bureau": bureau_code,
        "fields": fields,
        "inconsistencies_present": inconsistencies_present,
        "actionable_basis_present": actionable_basis,
        "requires_user_confirmation": not user_confirmation_complete and confidence_level != "high",
        "confidence_level": confidence_level,
        "ownership_confirmed": True if identity_confirmed_for_bureau else "unknown",
        "user_confirmation_complete": user_confirmation_complete,
        "user_assertion_flags": user_assertions,
        "last_action_type": "NONE",
        "last_action_target": "BUREAU",
        "last_action_sent_at": None,
        "deadline_at": None,
        "response_received": False,
        "response_received_at": None,
        "response_resolved_issue": False,
        "verification_allowed": True,
        "action_possible": True,
        "action_now_is_suboptimal": False,
        "escalation_allowed": False,
        "receipt_snippet": "; ".join(receipt_snippets) if receipt_snippets else "",
    }
    return canonical
