"""
truth_posture.py | 850 Lab Parser Machine
Immutable Contracts - Node 2: Truth Posture Contract (CLOSED)

Validates letter language tiers against evidence and scans for forbidden assertions.
"""

from __future__ import annotations
import re
from typing import List
from constants import EVIDENCE_TIER_REQUIREMENTS, FORBIDDEN_ASSERTIONS
from evidence_chain import EvidenceChain


ALLOWED_ASSERTION_PATTERNS = {
    "TIER_A": [
        r"reported as\b",
    ],
    "TIER_B": [
        r"consumer states\b",
    ],
    "TIER_C": [
        r"inconsistent",
        r"conflicting",
    ],
    "TIER_D": [
        r"could not be verified",
        r"no documentation provided",
    ],
}

FORBIDDEN_PATTERNS = [
    re.compile(re.escape(phrase), re.IGNORECASE) for phrase in FORBIDDEN_ASSERTIONS
]

FORBIDDEN_REGEX_PATTERNS = [
    re.compile(r"you failed to comply with\s*§", re.IGNORECASE),
    re.compile(r"failed to comply with\s*§", re.IGNORECASE),
    re.compile(r"\bnegligen(?:t|ce)\b", re.IGNORECASE),
    re.compile(r"\bfraud(?:ulent)?\b", re.IGNORECASE),
    re.compile(r"\billegal\b", re.IGNORECASE),
    re.compile(r"statutory\s+breach", re.IGNORECASE),
    re.compile(r"\bintent(?:ional(?:ly)?)?\b.*\b(?:violat|breach|fail)", re.IGNORECASE),
    re.compile(r"\b(?:violat|breach|fail).*\bintent(?:ional(?:ly)?)?\b", re.IGNORECASE),
    re.compile(r"must\s+delete", re.IGNORECASE),
    re.compile(r"required\s+(?:by\s+law\s+)?to\s+(?:delete|remove)", re.IGNORECASE),
    re.compile(r"violates?\s+the\s+(?:FCRA|fair\s+credit)", re.IGNORECASE),
]


def validate_letter_language_tier(chain: EvidenceChain, tier: str) -> bool:
    requirements = EVIDENCE_TIER_REQUIREMENTS.get(tier)
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


def forbidden_assertions_scan(letter_text: str) -> bool:
    if not letter_text:
        return True

    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(letter_text):
            return False

    for pattern in FORBIDDEN_REGEX_PATTERNS:
        if pattern.search(letter_text):
            return False

    return True
