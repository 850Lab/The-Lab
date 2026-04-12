"""
Phase 12 — scenario output schema (structured only, no prose).

All emitted objects are JSON-serializable dicts with stable keys.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

SCENARIO_OBJECT_VERSION = "1.0.0"
DETECTOR_VERSION_DEFAULT = "scenario_recognition@1.0.0+rules@1.0.0"

# scenario.status
STATUS_DETECTED = "detected"
STATUS_BLOCKED_INSUFFICIENT_EVIDENCE = "blocked_by_insufficient_evidence"
STATUS_CANDIDATE = "candidate"

# scope_type
SCOPE_WORKFLOW = "workflow"
SCOPE_ACCOUNT_FINGERPRINT = "account_fingerprint"


def scenario_dict(
    *,
    scenario_id: str,
    scenario_type: str,
    status: str,
    priority: int,
    scope_type: str,
    scope_key: str,
    triggering_fields: List[Dict[str, Any]],
    evidence: Dict[str, Any],
    reason_code: str,
    detected_at: str,
    detector_version: str,
    rule_id: str,
    rule_version: str,
    evaluation_run_id: str,
    input_digest: str,
    bureaus_compared: Optional[List[str]] = None,
    blocking_reasons: Optional[List[str]] = None,
    related_account_fingerprint: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "scenario_id": scenario_id,
        "version": SCENARIO_OBJECT_VERSION,
        "scenario_type": scenario_type,
        "status": status,
        "priority": int(priority),
        "scope_type": scope_type,
        "scope_key": scope_key,
        "triggering_fields": list(triggering_fields),
        "evidence": dict(evidence),
        "reason_code": reason_code,
        "detected_at": detected_at,
        "detector_version": detector_version,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "evaluation_run_id": evaluation_run_id,
        "input_digest": input_digest,
    }
    if bureaus_compared is not None:
        out["bureaus_compared"] = sorted(bureaus_compared)
    if blocking_reasons:
        out["blocking_reasons"] = list(blocking_reasons)
    if related_account_fingerprint is not None:
        out["related_account_fingerprint"] = related_account_fingerprint
    if tags:
        out["tags"] = sorted(tags)
    return out
