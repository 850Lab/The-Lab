"""
Pivot rule definitions loaded from versioned JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PivotRule:
    rule_id: str
    version: str
    status: str
    applicable_scenarios: List[Dict[str, Any]]
    required_conditions: List[Dict[str, Any]]
    exclusion_conditions: List[Dict[str, Any]]
    pivot_type: str
    directives_template: List[Dict[str, Any]]
    priority: int
    reason_code_template: str
    allow_canonical_gates: bool = False


def rule_from_dict(d: Dict[str, Any]) -> PivotRule:
    return PivotRule(
        rule_id=str(d["rule_id"]),
        version=str(d["version"]),
        status=str(d.get("status") or "draft"),
        applicable_scenarios=list(d.get("applicable_scenarios") or []),
        required_conditions=list(d.get("required_conditions") or []),
        exclusion_conditions=list(d.get("exclusion_conditions") or []),
        pivot_type=str(d["pivot_type"]),
        directives_template=list(d.get("directives_template") or []),
        priority=int(d.get("priority") or 100),
        reason_code_template=str(d.get("reason_code_template") or "UNKNOWN"),
        allow_canonical_gates=bool(d.get("allow_canonical_gates")),
    )


def load_pivot_rules_json(path: Optional[Path] = None) -> List[PivotRule]:
    if path is None:
        path = Path(__file__).resolve().parent / "registry" / "v1" / "pivot_rules.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("pivot_rules.json must be a JSON array")
    return [rule_from_dict(x) for x in data if isinstance(x, dict)]


def active_pivot_rules(rules: List[PivotRule]) -> List[PivotRule]:
    return [r for r in rules if r.status == "active"]


def load_compatibility_matrix(path: Optional[Path] = None) -> Dict[str, Any]:
    if path is None:
        path = Path(__file__).resolve().parent / "registry" / "v1" / "compatibility_v1.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
