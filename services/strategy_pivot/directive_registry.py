"""
Load and validate directive category / enum vocabulary (V1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _registry_path() -> Path:
    return Path(__file__).resolve().parent / "registry" / "directive_enums_v1.json"


def load_directive_registry(path: Path | None = None) -> Dict[str, Any]:
    p = path or _registry_path()
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def validate_directive(directive: Dict[str, Any], registry: Dict[str, Any]) -> Tuple[bool, str]:
    cat = str(directive.get("category") or "")
    val = directive.get("value")
    params = directive.get("params")
    if not cat:
        return False, "missing_category"
    if not isinstance(val, dict):
        return False, "value_not_object"
    if params is not None and not isinstance(params, dict):
        return False, "params_not_object"

    reg = registry.get(cat)
    if not isinstance(reg, dict):
        return False, "unknown_category"

    if cat == "target_focus":
        mode = val.get("mode")
        if mode not in (reg.get("modes") or []):
            return False, "invalid_target_focus_mode"
    elif cat == "dispute_framing_type":
        t = val.get("type")
        if t not in (reg.get("types") or []):
            return False, "invalid_framing_type"
    elif cat == "escalation_path_preference":
        p = val.get("preference")
        if p not in (reg.get("preferences") or []):
            return False, "invalid_escalation_preference"
    elif cat == "grouping_strategy":
        s = val.get("strategy")
        if s not in (reg.get("strategies") or []):
            return False, "invalid_grouping_strategy"
    elif cat == "priority_adjustment":
        adj = val.get("adjustment")
        mag = val.get("magnitude")
        if adj not in (reg.get("adjustments") or []):
            return False, "invalid_priority_adjustment"
        if mag is not None and mag not in (reg.get("magnitudes") or []):
            return False, "invalid_magnitude"
    elif cat == "sequencing_hint":
        h = val.get("hint")
        if h not in (reg.get("hints") or []):
            return False, "invalid_sequencing_hint"
    else:
        return False, "unhandled_category"

    return True, ""


def assert_directives_structured(directives: List[Dict[str, Any]], registry: Dict[str, Any]) -> None:
    for d in directives:
        ok, err = validate_directive(d, registry)
        if not ok:
            raise ValueError(f"invalid_directive:{err}:{d!r}")
