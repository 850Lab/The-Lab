"""
Pure scenario detection: ``detect_scenarios(evaluation_context) -> list[dict]``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import cross_bureau as cb
from . import non_bureau as nb
from .rule_model import ScenarioRule, active_rules, load_rules_json
from .schema import (
    DETECTOR_VERSION_DEFAULT,
    SCOPE_ACCOUNT_FINGERPRINT,
    STATUS_BLOCKED_INSUFFICIENT_EVIDENCE,
    STATUS_DETECTED,
    scenario_dict,
)
from .scope_builder import Scope, build_scopes


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_input_digest(context: Dict[str, Any]) -> str:
    payload = {
        "canonical_snapshot": context.get("canonical_snapshot") or {},
        "cross_bureau_slices": context.get("cross_bureau_slices") or [],
        "workflow_id": context.get("workflow_id"),
        "evaluation_run_id": context.get("evaluation_run_id"),
    }
    h = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{h}"


def _scenario_id(
    *,
    evaluation_run_id: str,
    rule_id: str,
    rule_version: str,
    scope_type: str,
    scope_key: str,
    scenario_type: str,
    status: str,
    reason_code: str,
) -> str:
    raw = _canonical_json(
        {
            "evaluation_run_id": evaluation_run_id,
            "rule_id": rule_id,
            "rule_version": rule_version,
            "scope_type": scope_type,
            "scope_key": scope_key,
            "scenario_type": scenario_type,
            "status": status,
            "reason_code": reason_code,
        }
    )
    return f"scn_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:26]}"


def _iter_slice_conditions(conds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    for c in conds:
        if not isinstance(c, dict):
            continue
        k = c.get("kind")
        if k in ("slice_compare", "slice_present"):
            found.append(c)
        elif k in ("any_of", "all_of"):
            found.extend(_iter_slice_conditions(list(c.get("conditions") or [])))
    return found


def _slice_dimensions_from_rule(rule: ScenarioRule) -> List[Tuple[str, int]]:
    """(dimension, min_bureaus) from slice conditions (including nested any_of/all_of)."""
    out: List[Tuple[str, int]] = []
    m_default = max(2, rule.applicable_scope.min_bureaus)
    for c in _iter_slice_conditions(rule.required_conditions):
        k = c.get("kind")
        if k == "slice_compare":
            dim = str(c.get("dimension") or "")
            mb = int(c.get("min_bureaus_with_value") or m_default)
            if dim:
                out.append((dim, max(m_default, mb)))
        elif k == "slice_present":
            dim = str(c.get("dimension") or "")
            mb = int(c.get("min_bureau_count") or m_default)
            if dim:
                out.append((dim, max(m_default, mb)))
    return out


def _insufficient_bureau_check(
    rule: ScenarioRule,
    slice_data: Dict[str, Any],
) -> Optional[str]:
    """
    If coverage insufficient for **all** slice dimensions referenced by the rule,
    return blocking reason. If at least one dimension has enough bureaus, return None
    (let rule evaluation proceed; specific branches may still fail).
    """
    if rule.applicable_scope.insufficient_evidence_policy != "blocked":
        return None
    pairs = _slice_dimensions_from_rule(rule)
    if not pairs:
        return None
    any_satisfied = False
    for dim, need in pairs:
        got = cb.count_bureaus_with_dimension(slice_data, dim)
        if got >= need:
            any_satisfied = True
            break
    if any_satisfied:
        return None
    return "INSUFFICIENT_BUREAU_COVERAGE"


def _eval_condition(
    cond: Dict[str, Any],
    *,
    snapshot: Dict[str, Any],
    scope: Scope,
) -> Tuple[bool, Dict[str, Any]]:
    """Evaluate one condition; second return is evidence fragment."""
    kind = str(cond.get("kind") or "")
    ev: Dict[str, Any] = {"condition_kind": kind}

    if kind == "canonical_field":
        fid = str(cond.get("field_id") or "")
        op = str(cond.get("operator") or "eq")
        val = cond.get("value")
        ok = nb.eval_canonical_field(snapshot, fid, op, val)
        ev["field_id"] = fid
        ev["operator"] = op
        ev["expected"] = val
        ev["actual"] = nb.field_value(snapshot, fid)
        return ok, ev

    if kind == "canonical_field_all":
        sub = cond.get("conditions") or []
        if not isinstance(sub, list):
            return False, ev
        ok = nb.eval_canonical_field_all(snapshot, [x for x in sub if isinstance(x, dict)])
        ev["subconditions"] = sub
        return ok, ev

    if kind == "eligibility_gate":
        fid = str(cond.get("field_id") or "")
        req = bool(cond.get("required_eligible", True))
        ok = nb.eval_eligibility_gate(snapshot, fid, req)
        ev["field_id"] = fid
        ev["required_eligible"] = req
        return ok, ev

    if kind == "field_ineligible":
        fid = str(cond.get("field_id") or "")
        ok = nb.field_marked_ineligible(snapshot, fid)
        ev["field_id"] = fid
        return ok, ev

    if kind == "any_of":
        branches = cond.get("conditions") or []
        if not isinstance(branches, list):
            return False, ev
        frags: List[Any] = []
        for b in branches:
            if not isinstance(b, dict):
                continue
            sub_ok, sub_ev = _eval_condition(b, snapshot=snapshot, scope=scope)
            frags.append(sub_ev)
            if sub_ok:
                ev["matched_branch_index"] = len(frags) - 1
                ev["branches"] = frags
                return True, ev
        ev["branches"] = frags
        return False, ev

    if kind == "all_of":
        branches = cond.get("conditions") or []
        if not isinstance(branches, list):
            return False, ev
        frags = []
        for b in branches:
            if not isinstance(b, dict):
                return False, ev
            sub_ok, sub_ev = _eval_condition(b, snapshot=snapshot, scope=scope)
            frags.append(sub_ev)
            if not sub_ok:
                ev["branches"] = frags
                return False, ev
        ev["branches"] = frags
        return True, ev

    if kind in ("slice_present", "slice_compare"):
        if not scope.slice_data:
            return False, ev
        sd = scope.slice_data
        dim = str(cond.get("dimension") or "")
        if not dim:
            return False, ev
        vals = cb.bureau_values_for_dimension(sd, dim)
        ev["dimension"] = dim
        ev["values_by_bureau"] = dict(sorted(vals.items()))

        if kind == "slice_present":
            need = int(cond.get("min_bureau_count") or 2)
            ok = len(vals) >= need
            ev["min_bureau_count"] = need
            ev["observed_bureau_count"] = len(vals)
            return ok, ev

        # slice_compare
        need = int(cond.get("min_bureaus_with_value") or 2)
        if len(vals) < need:
            ev["min_bureaus_with_value"] = need
            return False, ev
        cmp = str(cond.get("compare") or "string_mismatch")
        tol = int(cond.get("tolerance") or 0)
        if cmp == "string_mismatch":
            ok = cb.mismatch_string_dimensions(vals)
        elif cmp == "numeric_mismatch":
            ok = cb.mismatch_numeric_dimensions(vals, tolerance=tol)
        elif cmp == "balance_or_past_due_mismatch":
            ok = cb.mismatch_mixed_balance_or_past_due(vals, tolerance=tol)
        else:
            ok = False
        ev["compare"] = cmp
        ev["tolerance"] = tol
        ev["mismatch"] = ok
        return ok, ev

    return False, ev


def _collect_triggering_fields(conditions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in conditions:
        if not isinstance(c, dict):
            continue
        if c.get("field_id") and "operator" in c and "kind" not in c:
            out.append({"field_id": str(c["field_id"]), "role": "required"})
            continue
        k = c.get("kind")
        if k == "canonical_field":
            out.append({"field_id": str(c.get("field_id") or ""), "role": "required"})
        elif k == "canonical_field_all":
            out.extend(_collect_triggering_fields(list(c.get("conditions") or [])))
        elif k in ("eligibility_gate", "field_ineligible"):
            out.append({"field_id": str(c.get("field_id") or ""), "role": "eligibility"})
        elif k in ("any_of", "all_of"):
            out.extend(_collect_triggering_fields(list(c.get("conditions") or [])))
    return [x for x in out if x.get("field_id")]


def _exclusions_fire(rule: ScenarioRule, snapshot: Dict[str, Any], scope: Scope) -> bool:
    for c in rule.exclusion_conditions:
        if not isinstance(c, dict):
            continue
        ok, _ = _eval_condition(c, snapshot=snapshot, scope=scope)
        if ok:
            return True
    return False


def _evaluate_rule_on_scope(
    rule: ScenarioRule,
    scope: Scope,
    *,
    snapshot: Dict[str, Any],
    context: Dict[str, Any],
    input_digest: str,
    detected_at: str,
    detector_version: str,
) -> Optional[Dict[str, Any]]:
    if scope.scope_type not in rule.applicable_scope.scope_types:
        return None

    if _exclusions_fire(rule, snapshot, scope):
        return None

    # Blocked insufficient evidence (cross-bureau only)
    if scope.scope_type == SCOPE_ACCOUNT_FINGERPRINT and scope.slice_data:
        br = _insufficient_bureau_check(rule, scope.slice_data)
        if br:
            reason = f"{rule.reason_code_template}_BLOCKED"
            sid = _scenario_id(
                evaluation_run_id=str(context.get("evaluation_run_id") or ""),
                rule_id=rule.rule_id,
                rule_version=rule.version,
                scope_type=scope.scope_type,
                scope_key=scope.scope_key,
                scenario_type=rule.scenario_type,
                status=STATUS_BLOCKED_INSUFFICIENT_EVIDENCE,
                reason_code=reason,
            )
            bureaus = cb.bureaus_in_slice(scope.slice_data)
            return scenario_dict(
                scenario_id=sid,
                scenario_type=rule.scenario_type,
                status=STATUS_BLOCKED_INSUFFICIENT_EVIDENCE,
                priority=rule.priority,
                scope_type=scope.scope_type,
                scope_key=scope.scope_key,
                triggering_fields=[],
                evidence={
                    "slice_refs": [
                        {
                            "slice_type": "cross_bureau_account",
                            "slice_key": scope.scope_key,
                            "version": "v1",
                        }
                    ],
                    "blocking_detail": br,
                },
                reason_code=reason,
                detected_at=detected_at,
                detector_version=detector_version,
                rule_id=rule.rule_id,
                rule_version=rule.version,
                evaluation_run_id=str(context.get("evaluation_run_id") or ""),
                input_digest=input_digest,
                bureaus_compared=bureaus,
                blocking_reasons=[br],
                related_account_fingerprint=scope.scope_key,
                tags=["cross_bureau", "insufficient_evidence"],
            )

    req_evidence: List[Any] = []
    for c in rule.required_conditions:
        if not isinstance(c, dict):
            return None
        ok, frag = _eval_condition(c, snapshot=snapshot, scope=scope)
        req_evidence.append(frag)
        if not ok:
            return None

    opt_evidence: List[Any] = []
    for c in rule.optional_conditions:
        if not isinstance(c, dict):
            continue
        ok, frag = _eval_condition(c, snapshot=snapshot, scope=scope)
        if ok:
            opt_evidence.append(frag)

    trig = _collect_triggering_fields(rule.required_conditions + rule.optional_conditions)
    evidence: Dict[str, Any] = {
        "required_condition_traces": req_evidence,
        "optional_condition_traces": opt_evidence,
    }
    if scope.slice_data:
        evidence["slice_refs"] = [
            {
                "slice_type": "cross_bureau_account",
                "slice_key": scope.scope_key,
                "version": "v1",
            }
        ]
        evidence["comparisons"] = [x for x in req_evidence if x.get("condition_kind") == "slice_compare"]

    reason = rule.reason_code_template
    sid = _scenario_id(
        evaluation_run_id=str(context.get("evaluation_run_id") or ""),
        rule_id=rule.rule_id,
        rule_version=rule.version,
        scope_type=scope.scope_type,
        scope_key=scope.scope_key,
        scenario_type=rule.scenario_type,
        status=STATUS_DETECTED,
        reason_code=reason,
    )
    bureaus = None
    tags: List[str] = []
    if scope.scope_type == SCOPE_ACCOUNT_FINGERPRINT:
        tags.append("cross_bureau")
        if scope.slice_data:
            bureaus = cb.bureaus_in_slice(scope.slice_data)
    else:
        tags.append("workflow")

    return scenario_dict(
        scenario_id=sid,
        scenario_type=rule.scenario_type,
        status=STATUS_DETECTED,
        priority=rule.priority,
        scope_type=scope.scope_type,
        scope_key=scope.scope_key,
        triggering_fields=trig,
        evidence=evidence,
        reason_code=reason,
        detected_at=detected_at,
        detector_version=detector_version,
        rule_id=rule.rule_id,
        rule_version=rule.version,
        evaluation_run_id=str(context.get("evaluation_run_id") or ""),
        input_digest=input_digest,
        bureaus_compared=bureaus,
        related_account_fingerprint=scope.scope_key if scope.scope_type == SCOPE_ACCOUNT_FINGERPRINT else None,
        tags=tags,
    )


def detect_scenarios(
    evaluation_context: Dict[str, Any],
    *,
    _rules: Optional[List[ScenarioRule]] = None,
) -> List[Dict[str, Any]]:
    """
    Deterministic scenario detection. No I/O unless loading default rules from disk.

    ``evaluation_context`` keys:
    - ``canonical_snapshot``: field_id -> {{ "value": ..., "legally_eligible": bool }} or bare value
    - ``cross_bureau_slices``: list of slice dicts (see cross_bureau module)
    - ``workflow_id``: optional str
    - ``evaluation_run_id``: str
    - ``detected_at``: optional ISO-8601 (for reproducible tests)
    - ``detector_version``: optional str
    """
    rules = _rules if _rules is not None else active_rules(load_rules_json())
    snapshot = evaluation_context.get("canonical_snapshot") or {}
    if not isinstance(snapshot, dict):
        snapshot = {}

    detected_at = str(
        evaluation_context.get("detected_at") or _utc_now_iso()
    )
    detector_version = str(
        evaluation_context.get("detector_version") or DETECTOR_VERSION_DEFAULT
    )
    input_digest = compute_input_digest(evaluation_context)

    scopes = build_scopes(evaluation_context)
    out: List[Dict[str, Any]] = []

    sorted_rules = sorted(rules, key=lambda r: (r.priority, r.rule_id))

    for rule in sorted_rules:
        for scope in scopes:
            rec = _evaluate_rule_on_scope(
                rule,
                scope,
                snapshot=snapshot,
                context=evaluation_context,
                input_digest=input_digest,
                detected_at=detected_at,
                detector_version=detector_version,
            )
            if rec is not None:
                out.append(rec)

    out.sort(
        key=lambda s: (
            int(s.get("priority") or 0),
            str(s.get("scenario_type") or ""),
            str(s.get("scope_key") or ""),
            str(s.get("rule_id") or ""),
            str(s.get("scenario_id") or ""),
        )
    )
    return out
