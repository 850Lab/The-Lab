"""
Non-bureau (workflow-scoped) canonical field evaluation — deterministic only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _get_field(snapshot: Dict[str, Any], field_id: str) -> Optional[Dict[str, Any]]:
    raw = snapshot.get(field_id)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    return {"value": raw, "legally_eligible": True}


def field_value(snapshot: Dict[str, Any], field_id: str) -> Any:
    cell = _get_field(snapshot, field_id)
    if cell is None:
        return None
    return cell.get("value")


def field_legally_eligible(snapshot: Dict[str, Any], field_id: str) -> bool:
    cell = _get_field(snapshot, field_id)
    if cell is None:
        return False
    return bool(cell.get("legally_eligible", True))


def compare(op: str, left: Any, right: Any) -> bool:
    op = str(op).strip().lower()
    if op == "eq":
        return left == right
    if op == "neq":
        return left != right
    if op == "is_true":
        return left is True
    if op == "is_false":
        return left is False
    if op == "is_null":
        return left is None
    if op == "is_non_null":
        return left is not None
    if op == "gte":
        try:
            return float(left) >= float(right)
        except (TypeError, ValueError):
            return False
    if op == "lte":
        try:
            return float(left) <= float(right)
        except (TypeError, ValueError):
            return False
    return False


def eval_canonical_field(
    snapshot: Dict[str, Any],
    field_id: str,
    operator: str,
    value: Any,
) -> bool:
    return compare(operator, field_value(snapshot, field_id), value)


def eval_canonical_field_all(
    snapshot: Dict[str, Any],
    subconds: List[Dict[str, Any]],
) -> bool:
    for c in subconds:
        if not isinstance(c, dict):
            return False
        fid = str(c.get("field_id") or "")
        op = str(c.get("operator") or "eq")
        val = c.get("value")
        if not eval_canonical_field(snapshot, fid, op, val):
            return False
    return True


def eval_eligibility_gate(snapshot: Dict[str, Any], field_id: str, required_eligible: bool) -> bool:
    ok = field_legally_eligible(snapshot, field_id)
    return ok if required_eligible else not ok


def field_marked_ineligible(snapshot: Dict[str, Any], field_id: str) -> bool:
    """True when the field is present and explicitly not legally eligible."""
    cell = _get_field(snapshot, field_id)
    if cell is None:
        return False
    return cell.get("legally_eligible") is False
