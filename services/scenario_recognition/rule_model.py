"""
Load and validate scenario rule definitions (versioned JSON).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ApplicableScope:
    scope_types: List[str]
    min_bureaus: int = 2
    insufficient_evidence_policy: str = "omit"  # omit | blocked
    requires_legal_eligibility: bool = False


@dataclass
class ScenarioRule:
    rule_id: str
    version: str
    status: str
    scenario_type: str
    applicable_scope: ApplicableScope
    required_conditions: List[Dict[str, Any]]
    optional_conditions: List[Dict[str, Any]]
    exclusion_conditions: List[Dict[str, Any]]
    priority: int
    reason_code_template: str


def _parse_scope(raw: Dict[str, Any]) -> ApplicableScope:
    st = raw.get("scope_types") or []
    if not isinstance(st, list):
        st = []
    return ApplicableScope(
        scope_types=[str(x) for x in st],
        min_bureaus=int(raw.get("min_bureaus") or 2),
        insufficient_evidence_policy=str(raw.get("insufficient_evidence_policy") or "omit"),
        requires_legal_eligibility=bool(raw.get("requires_legal_eligibility")),
    )


def rule_from_dict(d: Dict[str, Any]) -> ScenarioRule:
    return ScenarioRule(
        rule_id=str(d["rule_id"]),
        version=str(d["version"]),
        status=str(d.get("status") or "draft"),
        scenario_type=str(d["scenario_type"]),
        applicable_scope=_parse_scope(d.get("applicable_scope") or {}),
        required_conditions=list(d.get("required_conditions") or []),
        optional_conditions=list(d.get("optional_conditions") or []),
        exclusion_conditions=list(d.get("exclusion_conditions") or []),
        priority=int(d.get("priority") or 100),
        reason_code_template=str(d.get("reason_code_template") or "UNKNOWN"),
    )


def load_rules_json(path: Optional[Path] = None) -> List[ScenarioRule]:
    if path is None:
        path = Path(__file__).resolve().parent / "registry" / "v1" / "rules.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("rules.json must be a JSON array")
    return [rule_from_dict(x) for x in data if isinstance(x, dict)]


def active_rules(rules: List[ScenarioRule]) -> List[ScenarioRule]:
    return [r for r in rules if r.status == "active"]
