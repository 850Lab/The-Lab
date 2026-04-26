"""
User-facing recommendation payloads: rationale, confidence, and impact (deterministic, no LLM).
Aligned with product thresholds for confidence level (0–1) and clear, non-legalist copy.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

from review_claims import (
    CreditImpact,
    CrossBureauStatus,
    ReviewClaim,
    Severity,
)

# Normalized 0..1: align with product Phase 2 (and claims.py spirit).
CONFIDENCE_SCORE_HIGH = 0.75
CONFIDENCE_SCORE_MEDIUM = 0.4


def confidence_01_from_review_claim(rc: ReviewClaim) -> float:
    conf = None
    if rc.evidence_summary and rc.evidence_summary.claim_confidence_summary:
        conf = rc.evidence_summary.claim_confidence_summary
    if not conf:
        return 0.5
    h, m, lo = int(conf.high), int(conf.medium), int(conf.low)
    tot = max(1, h + m + lo)
    return min(1.0, (h * 1.0 + m * 0.55 + lo * 0.22) / tot)


def confidence_level_from_01(score: float) -> str:
    if score >= CONFIDENCE_SCORE_HIGH:
        return "high"
    if score >= CONFIDENCE_SCORE_MEDIUM:
        return "medium"
    return "low"


def impact_level_for_claim(rc: ReviewClaim) -> str:
    s = rc.impact_assessment.severity
    c = rc.impact_assessment.credit_impact
    if s == Severity.HIGH or c == CreditImpact.NEGATIVE:
        return "high" if s != Severity.LOW else "medium"
    if s == Severity.MODERATE:
        return "medium"
    if s == Severity.LOW and c == CreditImpact.UNKNOWN:
        return "low"
    return "low"


def _type_label(rt: str) -> str:
    m = {
        "negative_impact": "Score impact",
        "accuracy_verification": "Accuracy",
        "duplicate_account": "Duplicate account",
        "unverifiable_information": "Hard to verify",
        "account_ownership": "Ownership",
        "identity_verification": "Identity",
    }
    return m.get((rt or "").strip(), (rt or "issue").replace("_", " ").title())


def _consumer_reason_lines(rc: ReviewClaim) -> List[str]:
    reasons: List[str] = []
    if rc.impact_assessment.credit_impact == CreditImpact.NEGATIVE:
        reasons.append("May be hurting your score or profile as reported")
    if rc.impact_assessment.severity in (Severity.HIGH, Severity.MODERATE):
        reasons.append("Flagged with higher concern on your report")
    if (
        rc.evidence_summary
        and rc.evidence_summary.cross_bureau_status == CrossBureauStatus.MULTI_BUREAU
    ):
        reasons.append("Shows up on more than one bureau")
    if rc.letter_eligibility and rc.letter_eligibility.letter_ready:
        reasons.append("Meets what we need to draft a clear dispute for this item")
    conf = (
        rc.evidence_summary.claim_confidence_summary if rc.evidence_summary else None
    )
    if conf and conf.high > 0:
        reasons.append("Your report shows enough detail for a solid dispute on this one")
    if not reasons and rc.summary:
        reasons.append("Review this line against what you know about your history")
    if not reasons:
        reasons.append("Eligible to include in this round if it fits your goals")
    return reasons


def build_why_pair(rc: ReviewClaim) -> Tuple[str, str]:
    lines = _consumer_reason_lines(rc)
    short = lines[0] if lines else (rc.summary[:110] if rc.summary else "Review this item for your round.")
    if len(short) > 140:
        short = short[:137].rstrip() + "…"
    detailed = " ".join(lines) if lines else (rc.summary or short)
    return short, detailed


def build_recommendation_item(
    rc: ReviewClaim,
    suggested_ids: Set[str],
    per_claim_detailed: Dict[str, str],
) -> Dict[str, Any]:
    c01 = confidence_01_from_review_claim(rc)
    level = confidence_level_from_01(c01)
    short, detailed = build_why_pair(rc)
    alt_detailed = per_claim_detailed.get(str(rc.review_claim_id), "").strip()
    if alt_detailed:
        detailed = re.sub(r"\(score:\s*[\d.]+\)\s*$", "", alt_detailed).strip() or detailed

    acc = (rc.entities.get("account_name") or "").strip() or (
        rc.entities.get("bureau") or ""
    ).strip() or "Credit report item"
    rid = str(rc.review_claim_id)
    recommended = rid in suggested_ids
    return {
        "id": rid,
        "accountName": acc,
        "issueType": _type_label(str(rc.review_type.value if hasattr(rc.review_type, "value") else rc.review_type)),
        "summary": (rc.summary or rc.question or "").strip() or "Credit reporting item to review",
        "why": {
            "short": short,
            "detailed": detailed,
        },
        "confidence": {
            "level": level,
            "score": round(c01, 3),
        },
        "impactLevel": impact_level_for_claim(rc),
        "recommended": recommended,
        "optional": not recommended,
    }
