"""
evidence_chain.py | 850 Lab Parser Machine
Immutable Contracts - Node 6: Evidence Chain Requirements (CLOSED)

Builds and validates evidence chains per claim.
No free text. All provenance must be traceable.
"""

from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from constants import (
    EVIDENCE_TIERS,
    EVIDENCE_TIER_REQUIREMENTS,
)


@dataclass
class EvidenceChain:
    claim_id: str
    evidence_tiers_present: List[str] = field(default_factory=list)
    provenance_refs: List[str] = field(default_factory=list)
    user_assertion_flags: List[str] = field(default_factory=list)
    prior_action_refs: List[str] = field(default_factory=list)
    timing_refs: Dict[str, Optional[str]] = field(default_factory=dict)


def _generate_provenance_ref(claim_id: str, snippet: str) -> str:
    content = f"{claim_id}:{snippet}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def build_evidence_chain(claim: Dict[str, Any], context: Dict[str, Any]) -> EvidenceChain:
    claim_id = claim.get("claim_id", "")
    evidence_tiers = []
    provenance_refs = []

    fields = claim.get("fields", {})
    has_report_fields = bool(fields) and any(
        v for k, v in fields.items()
        if v is not None and str(v).strip() and k not in ("claim_id", "claim_type", "bureau")
    )
    if has_report_fields:
        evidence_tiers.append("TIER_A")
        receipt = claim.get("receipt_snippet", "")
        if receipt:
            provenance_refs.append(_generate_provenance_ref(claim_id, receipt))
        else:
            for k, v in sorted(fields.items()):
                if v is not None and str(v).strip():
                    provenance_refs.append(_generate_provenance_ref(claim_id, f"{k}={v}"))
                    break

    user_assertions = claim.get("user_assertion_flags", [])

    if user_assertions:
        evidence_tiers.append("TIER_B")
        for flag in user_assertions:
            provenance_refs.append(_generate_provenance_ref(claim_id, f"assertion:{flag}"))

    inconsistencies = claim.get("inconsistencies_present", False)
    last_action = claim.get("last_action_type", "NONE")
    response_received = claim.get("response_received", False)
    response_resolved = claim.get("response_resolved_issue", False)

    if inconsistencies:
        evidence_tiers.append("TIER_C")
        provenance_refs.append(_generate_provenance_ref(claim_id, "inconsistency_detected"))

    if last_action == "VERIFY" and response_received and not response_resolved:
        if "TIER_C" not in evidence_tiers:
            evidence_tiers.append("TIER_C")
        provenance_refs.append(_generate_provenance_ref(claim_id, "failed_verification"))

    deadline = claim.get("deadline_at")
    if deadline and not response_received:
        evidence_tiers.append("TIER_D")
        provenance_refs.append(_generate_provenance_ref(claim_id, "no_response_by_deadline"))

    prior_action_refs = []
    if last_action != "NONE":
        action_target = claim.get("last_action_target", "BUREAU")
        sent_at = claim.get("last_action_sent_at")
        ref = _generate_provenance_ref(claim_id, f"action:{last_action}:{action_target}:{sent_at}")
        prior_action_refs.append(ref)

    timing_refs = {}
    sent_at = claim.get("last_action_sent_at")
    if sent_at:
        timing_refs["sent_at"] = str(sent_at)
    if deadline:
        timing_refs["deadline_at"] = str(deadline)

    unique_tiers = list(dict.fromkeys(evidence_tiers))

    return EvidenceChain(
        claim_id=claim_id,
        evidence_tiers_present=unique_tiers,
        provenance_refs=provenance_refs,
        user_assertion_flags=user_assertions,
        prior_action_refs=prior_action_refs,
        timing_refs=timing_refs,
    )


def validate_evidence_chain(chain: EvidenceChain, letter_language_tier: str) -> bool:
    if not chain.provenance_refs:
        return False

    requirements = EVIDENCE_TIER_REQUIREMENTS.get(letter_language_tier)
    if not requirements:
        return False

    tiers_present = set(chain.evidence_tiers_present)

    if "all_of" in requirements:
        if not all(t in tiers_present for t in requirements["all_of"]):
            return False

    if "any_of" in requirements:
        if not any(t in tiers_present for t in requirements["any_of"]):
            return False

    if requirements.get("requires_prior_action", False):
        if not chain.prior_action_refs:
            return False

    return True
