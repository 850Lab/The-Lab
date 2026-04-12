"""
Pure pivot evaluation: ``build_strategy_pivots(evaluation_context)``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from . import conflict_resolution as cr
from .context_adapter import build_pivot_evaluation_context
from .digest import compute_pivot_input_digest
from .directive_registry import assert_directives_structured, load_directive_registry
from .rule_model import PivotRule, active_pivot_rules, load_compatibility_matrix, load_pivot_rules_json
from .schema import PIVOT_ENGINE_VERSION_DEFAULT, pivot_dict


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _pivot_id(
    *,
    evaluation_run_id: str,
    rule_id: str,
    rule_version: str,
    scope_type: str,
    scope_key: str,
    pivot_type: str,
    reason_code: str,
    scenario_ids: List[str],
) -> str:
    raw = _canonical_json(
        {
            "evaluation_run_id": evaluation_run_id,
            "rule_id": rule_id,
            "rule_version": rule_version,
            "scope_type": scope_type,
            "scope_key": scope_key,
            "pivot_type": pivot_type,
            "reason_code": reason_code,
            "scenario_ids": sorted(scenario_ids),
        }
    )
    return f"pvt_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:26]}"


def _scenario_matches_matcher(s: Dict[str, Any], m: Dict[str, Any]) -> bool:
    if str(s.get("scenario_type") or "") != str(m.get("scenario_type") or ""):
        return False
    allowed = m.get("allowed_statuses") or ["detected"]
    if not isinstance(allowed, list):
        allowed = ["detected"]
    return str(s.get("status") or "") in {str(x) for x in allowed}


def _scenarios_for_matchers(
    scenarios: List[Dict[str, Any]],
    matchers: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    if not matchers:
        return []
    per: List[List[Dict[str, Any]]] = []
    for m in matchers:
        if not isinstance(m, dict):
            return None
        need = int(m.get("min_count") or 1)
        hits = [s for s in scenarios if _scenario_matches_matcher(s, m)]
        if len(hits) < need:
            return None
        per.append(hits)
    if len(per) == 1:
        return per[0]
    key_sets = [
        {(str(s.get("scope_type") or ""), str(s.get("scope_key") or "")) for s in h}
        for h in per
    ]
    common = set.intersection(*key_sets) if key_sets else set()
    if not common:
        return None
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for h in per:
        for s in h:
            sk = (str(s.get("scope_type") or ""), str(s.get("scope_key") or ""))
            if sk not in common:
                continue
            sid = str(s.get("scenario_id") or "")
            if sid and sid not in seen:
                seen.add(sid)
                out.append(s)
    return out


def _eval_condition(
    cond: Dict[str, Any],
    *,
    scenarios: List[Dict[str, Any]],
    snapshot: Dict[str, Any],
    allow_canonical: bool,
) -> bool:
    kind = str(cond.get("kind") or "")
    if kind == "scenario_present":
        m = {
            "scenario_type": cond.get("scenario_type"),
            "allowed_statuses": cond.get("allowed_statuses") or ["detected"],
            "min_count": int(cond.get("min_count") or 1),
        }
        got = _scenarios_for_matchers(scenarios, [m])
        return got is not None

    if kind == "scenario_absent":
        st = str(cond.get("scenario_type") or "")
        allowed = cond.get("allowed_statuses") or ["detected"]
        for s in scenarios:
            if str(s.get("scenario_type") or "") == st and str(s.get("status") or "") in {
                str(x) for x in allowed
            }:
                return False
        return True

    if kind == "same_scope_as":
        ta = str(cond.get("scenario_type_a") or "")
        tb = str(cond.get("scenario_type_b") or "")
        keys_a = {
            (str(s.get("scope_type") or ""), str(s.get("scope_key") or ""))
            for s in scenarios
            if str(s.get("scenario_type") or "") == ta
        }
        keys_b = {
            (str(s.get("scope_type") or ""), str(s.get("scope_key") or ""))
            for s in scenarios
            if str(s.get("scenario_type") or "") == tb
        }
        return bool(keys_a & keys_b)

    if kind == "canonical_field":
        if not allow_canonical:
            return False
        fid = str(cond.get("field_id") or "")
        op = str(cond.get("operator") or "eq")
        val = cond.get("value")
        cell = snapshot.get(fid)
        cur = cell.get("value") if isinstance(cell, dict) else cell
        if op == "eq":
            return cur == val
        if op == "neq":
            return cur != val
        return False

    return False


def _exclusion_fires(
    rule: PivotRule,
    scenarios: List[Dict[str, Any]],
    snapshot: Dict[str, Any],
) -> bool:
    for c in rule.exclusion_conditions:
        if isinstance(c, dict) and _eval_condition(
            c,
            scenarios=scenarios,
            snapshot=snapshot,
            allow_canonical=rule.allow_canonical_gates,
        ):
            return True
    return False


def _required_ok(
    rule: PivotRule,
    scenarios: List[Dict[str, Any]],
    snapshot: Dict[str, Any],
) -> bool:
    if not rule.required_conditions:
        return True
    for c in rule.required_conditions:
        if not isinstance(c, dict):
            return False
        if not _eval_condition(
            c,
            scenarios=scenarios,
            snapshot=snapshot,
            allow_canonical=rule.allow_canonical_gates,
        ):
            return False
    return True


def _param_from_scenarios(
    scenarios_group: List[Dict[str, Any]],
    source_key: str,
) -> List[Any]:
    acc: List[Any] = []
    if source_key == "bureaus_compared":
        for s in scenarios_group:
            for b in s.get("bureaus_compared") or []:
                if b not in acc:
                    acc.append(b)
        return acc
    if source_key == "related_account_fingerprints":
        for s in scenarios_group:
            ra = s.get("related_account_fingerprint")
            if ra and ra not in acc:
                acc.append(ra)
            for x in s.get("related_account_fingerprints") or []:
                if x not in acc:
                    acc.append(x)
            ev = s.get("evidence") or {}
            if isinstance(ev, dict):
                for x in ev.get("unresolved_account_fingerprints") or []:
                    if x not in acc:
                        acc.append(x)
        return acc
    return acc


def _expand_directives(
    template: List[Dict[str, Any]],
    scenarios_group: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in template:
        if not isinstance(t, dict):
            continue
        d = {
            "category": str(t.get("category") or ""),
            "value": copy.deepcopy(t.get("value") or {}),
            "params": {},
        }
        ps = t.get("param_sources") or {}
        if isinstance(ps, dict):
            for pk, src in ps.items():
                d["params"][str(pk)] = _param_from_scenarios(scenarios_group, str(src))
        out.append(d)
    return out


def _group_matched_by_scope(matched: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    g: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for s in matched:
        k = (str(s.get("scope_type") or ""), str(s.get("scope_key") or ""))
        g.setdefault(k, []).append(s)
    return g


def build_strategy_pivots(
    evaluation_context: Dict[str, Any],
    *,
    _rules: Optional[List[PivotRule]] = None,
    _directive_registry: Optional[Dict[str, Any]] = None,
    _compatibility: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    evaluation_context keys:
    - evaluation_run_id (str)
    - as_of (str ISO)
    - scenarios (list of Phase 12 scenario dicts)
    - canonical_snapshot (optional dict)
    - pivot_engine_version (optional str)
    """
    scenarios = list(evaluation_context.get("scenarios") or [])
    snapshot = evaluation_context.get("canonical_snapshot") or {}
    if not isinstance(snapshot, dict):
        snapshot = {}
    erid = str(evaluation_context.get("evaluation_run_id") or "")
    as_of = str(evaluation_context.get("as_of") or "")
    engine = str(evaluation_context.get("pivot_engine_version") or PIVOT_ENGINE_VERSION_DEFAULT)

    reg = _directive_registry if _directive_registry is not None else load_directive_registry()
    matrix = _compatibility if _compatibility is not None else load_compatibility_matrix()
    rules = _rules if _rules is not None else active_pivot_rules(load_pivot_rules_json())

    scen_sorted = sorted(
        scenarios,
        key=lambda s: (
            int(s.get("priority") or 0),
            str(s.get("scenario_type") or ""),
            str(s.get("scope_key") or ""),
            str(s.get("scenario_id") or ""),
        ),
    )
    input_digest = compute_pivot_input_digest(scen_sorted, snapshot, erid)

    sorted_rules = sorted(rules, key=lambda r: (r.priority, r.rule_id))
    raw: List[Dict[str, Any]] = []

    for rule in sorted_rules:
        matched = _scenarios_for_matchers(scen_sorted, rule.applicable_scenarios)
        if matched is None:
            continue
        if _exclusion_fires(rule, scen_sorted, snapshot):
            continue
        if not _required_ok(rule, scen_sorted, snapshot):
            continue
        by_scope = _group_matched_by_scope(matched)
        for (_st, _sk), group in sorted(by_scope.items(), key=lambda x: (x[0][0], x[0][1])):
            scope_type, scope_key = _st, _sk
            directives = _expand_directives(rule.directives_template, group)
            assert_directives_structured(directives, reg)
            sids = sorted({str(s.get("scenario_id") or "") for s in group if s.get("scenario_id")})
            reason = rule.reason_code_template
            pid = _pivot_id(
                evaluation_run_id=erid,
                rule_id=rule.rule_id,
                rule_version=rule.version,
                scope_type=scope_type,
                scope_key=scope_key,
                pivot_type=rule.pivot_type,
                reason_code=reason,
                scenario_ids=sids,
            )
            src = [
                {
                    "scenario_id": s.get("scenario_id"),
                    "scenario_type": s.get("scenario_type"),
                    "scenario_status": s.get("status"),
                }
                for s in sorted(group, key=lambda x: str(x.get("scenario_id") or ""))
            ]
            raw.append(
                pivot_dict(
                    pivot_id=pid,
                    pivot_type=rule.pivot_type,
                    source_scenarios=src,
                    priority=rule.priority,
                    scope_type=scope_type,
                    scope_key=scope_key,
                    strategy_directives=directives,
                    reason_code=reason,
                    created_at=as_of,
                    pivot_engine_version=engine,
                    evaluation_run_id=erid,
                    input_digest=input_digest,
                    rule_id=rule.rule_id,
                    rule_version=rule.version,
                    trace=[{"step": "rule_match", "rule_id": rule.rule_id, "result": "emit"}],
                )
            )

    resolved = cr.apply_conflict_pipeline(raw, matrix)
    resolved.sort(
        key=lambda p: (
            int(p.get("priority") or 999),
            str(p.get("pivot_type") or ""),
            str(p.get("scope_key") or ""),
            str(p.get("pivot_id") or ""),
        )
    )
    return resolved


__all__ = ["build_strategy_pivots"]
