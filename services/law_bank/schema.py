"""
V1 enums and allowed vocabularies for law bank units and resolution context.
"""

from __future__ import annotations

from typing import Any, Dict, Final, FrozenSet

LAW_RESOLUTION_CONTEXT_SCHEMA_VERSION: Final[str] = "law_resolution_context_v1"

STATUS_VALUES: Final[FrozenSet[str]] = frozenset(
    {"draft", "in_review", "published", "deprecated"}
)

LEVERAGE_TYPE_VALUES: Final[FrozenSet[str]] = frozenset(
    {
        "obligation",
        "consumer_right",
        "remedy_channel",
        "timing_expectation",
        "informational",
    }
)

ENFORCEMENT_SHAPE_VALUES: Final[FrozenSet[str]] = frozenset(
    {
        "bureau_process",
        "furnisher_process",
        "collector_process",
        "identity_block_process",
        "escalation_channel",
        "informational",
    }
)

ALLOWED_CONTEXT_KEYS: Final[FrozenSet[str]] = frozenset(
    {
        "schemaVersion",
        "disputeRound",
        "authoritativeStepId",
        "hasBureauTarget",
        "hasFurnisherTarget",
        "identityContext",
        "escalationEligible",
        "hasCollectionAccountSignals",
        "hasInquirySignals",
        "subjectMatterTagsPresent",
        "outcomePatternFlags",
    }
)


def law_unit_ref_from_unit(unit: Dict[str, Any]) -> Dict[str, Any]:
    """Public attachment shape (no triggers, no review metadata, no full law text)."""
    return {
        "unitId": unit["unitId"],
        "version": unit["version"],
        "title": unit["title"],
        "summary": unit["summary"],
        "leverageImpact": unit["leverageImpact"],
        "leverageType": unit["leverageType"],
        "enforcementShape": unit["enforcementShape"],
        "primaryCitations": list(unit.get("primaryCitations") or []),
    }
