"""
Rule-based, auditable classification for bureau/furnisher responses.

No hidden chain-of-thought: outputs are short, user-safe strings suitable for storage
and display. Callers may supply structured hints in parsed_summary; optional
manual_classification is trusted only from backend/admin paths.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Final, List, Tuple

RESPONSE_CLASSIFICATIONS: Final[Tuple[str, ...]] = (
    "favorable_resolved",
    "partial_resolution",
    "verification_only",
    "stall_or_non_answer",
    "adverse_or_rejected",
    "insufficient_to_classify",
)


@dataclass(frozen=True)
class ClassificationOutcome:
    classification: str
    reasoning_safe: str
    confidence: float
    recommended_next_action: str


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def _collect_text(parsed_summary: Dict[str, Any]) -> str:
    parts: List[str] = []
    if isinstance(parsed_summary.get("summary_safe"), str):
        parts.append(parsed_summary["summary_safe"])
    kws = parsed_summary.get("outcome_keywords")
    if isinstance(kws, list):
        parts.extend(str(x) for x in kws if x is not None)
    nested = parsed_summary.get("extracted_phrases_safe")
    if isinstance(nested, list):
        parts.extend(str(x) for x in nested if x is not None)
    return _norm_text(" ".join(parts))


def classify_parsed_response(parsed_summary: Dict[str, Any]) -> ClassificationOutcome:
    """
    Classify using keyword heuristics over caller-supplied safe text only.

    parsed_summary keys (all optional):
      - manual_classification: one of RESPONSE_CLASSIFICATIONS (trusted operator hint)
      - summary_safe: single-line sanitized summary
      - outcome_keywords: list of short strings
      - extracted_phrases_safe: list of short sanitized phrases
    """
    if not isinstance(parsed_summary, dict):
        parsed_summary = {}

    manual = parsed_summary.get("manual_classification")
    if isinstance(manual, str) and manual in RESPONSE_CLASSIFICATIONS:
        return ClassificationOutcome(
            classification=manual,
            reasoning_safe="Classification supplied by a verified backend or operator record.",
            confidence=0.95,
            recommended_next_action="apply_escalation_policy",
        )

    blob = _collect_text(parsed_summary)
    if len(blob) < 8:
        return ClassificationOutcome(
            classification="insufficient_to_classify",
            reasoning_safe="Not enough structured text was provided to classify this response reliably.",
            confidence=0.2,
            recommended_next_action="request_manual_review_or_more_detail",
        )

    # Order matters: first strong match wins (deterministic).
    rules: List[Tuple[str, Tuple[str, ...], str, float, str]] = [
        (
            "favorable_resolved",
            (
                "deleted",
                "removed",
                "will delete",
                "deletion",
                "updated to reflect deletion",
                "investigation complete",
                "no longer reporting",
                "has been corrected",
            ),
            "Language suggests items were deleted, removed, or corrected in your favor.",
            0.72,
            "confirm_on_next_report",
        ),
        (
            "adverse_or_rejected",
            (
                "frivolous",
                "not reinvestigate",
                "no violation",
                "unverifiable",
                "refuses to",
                "will not investigate",
                "insufficient basis",
            ),
            "Language suggests the dispute was rejected, deemed frivolous, or refused.",
            0.68,
            "consider_escalation",
        ),
        (
            "verification_only",
            (
                "verified as accurate",
                "furnisher verified",
                "found to be accurate",
                "confirmed as accurate",
                "substantiated",
            ),
            "Language focuses on verification that tradelines are accurate as reported.",
            0.65,
            "consider_method_of_verification",
        ),
        (
            "partial_resolution",
            (
                "some items",
                "partially",
                "one account",
                "updated except",
                "remaining items",
            ),
            "Language suggests only part of the disputed information was updated or addressed.",
            0.6,
            "review_remaining_items",
        ),
        (
            "stall_or_non_answer",
            (
            "need more information",
            "unable to investigate",
            "pending further",
            "additional documentation",
            "extend",
            "30 days",
            "more time",
            ),
            "Language suggests delay, a request for more information, or a non-substantive reply.",
            0.55,
            "follow_up_or_upload_docs",
        ),
    ]

    for label, needles, reason, conf, action in rules:
        if any(n in blob for n in needles):
            return ClassificationOutcome(
                classification=label,
                reasoning_safe=reason,
                confidence=conf,
                recommended_next_action=action,
            )

    return ClassificationOutcome(
        classification="insufficient_to_classify",
        reasoning_safe="The response text did not match known outcome patterns; manual review is appropriate.",
        confidence=0.35,
        recommended_next_action="request_manual_review_or_more_detail",
    )
