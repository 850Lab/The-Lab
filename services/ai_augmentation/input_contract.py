"""
Strict whitelist for model-facing payloads and stable input_digest.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Set

# Top-level keys permitted on the raw request before sanitization
ALLOWED_REQUEST_TOP_LEVEL = frozenset(
    {
        "workflow_id",
        "evaluation_run_id",
        "output_category",
        "guidance_view",
        "scenarios",
        "pivots",
        "canonical_summary",
        "created_at",
    }
)

# Keys stripped from nested objects anywhere (substring match on key path leaf)
_DISALLOWED_LEAF_NAMES = frozenset(
    {
        "password",
        "secret",
        "api_key",
        "apikey",
        "token",
        "authorization",
        "raw_report_text",
        "raw_document",
        "document_bytes",
        "mutation_token",
        "webhook_url",
        "side_effect_endpoint",
        "execution_handle",
        "private_key",
    }
)

# Substrings that disqualify a string value at leaf (redact entire leaf)
_DISALLOWED_VALUE_SUBSTRINGS = (
    "BEGIN RSA PRIVATE",
    "BEGIN OPENSSH PRIVATE",
    "sk-live-",
    "sk_test_",
)


def _strip_dict(obj: Any, *, path: str = "") -> Any:
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in _DISALLOWED_LEAF_NAMES:
                continue
            if any(d in lk for d in ("password", "secret", "token", "api_key", "webhook")):
                continue
            out[k] = _strip_dict(v, path=f"{path}.{k}" if path else k)
        return out
    if isinstance(obj, list):
        return [_strip_dict(x, path=path) for x in obj]
    if isinstance(obj, str):
        for sub in _DISALLOWED_VALUE_SUBSTRINGS:
            if sub in obj:
                return "[REDACTED]"
        return obj
    if obj is None or isinstance(obj, (bool, int)):
        return obj
    return str(obj)


def _whitelist_guidance_view(gv: Dict[str, Any]) -> Dict[str, Any]:
    """Subset of guidance view safe for augmentation context."""
    allowed_top = {
        "guidance_view_id",
        "version",
        "workflow_id",
        "global_priority_order",
        "input_digest",
        "evaluation_run_id",
        "refinement_version",
        "primary_groups",
        "secondary_groups",
        "grouped_guidance",
    }
    raw = {k: gv[k] for k in allowed_top if k in gv}
    stripped = _strip_dict(raw)
    if isinstance(stripped, dict) and "grouped_guidance" in stripped:
        groups = stripped["grouped_guidance"]
        if isinstance(groups, list):
            slim_groups: List[Dict[str, Any]] = []
            for g in groups:
                if not isinstance(g, dict):
                    continue
                slim_groups.append(
                    {
                        "group_id": g.get("group_id"),
                        "scope_type": g.get("scope_type"),
                        "scope_key": g.get("scope_key"),
                        "display_category": g.get("display_category"),
                        "guidance_ids": g.get("guidance_ids"),
                    }
                )
            stripped["grouped_guidance"] = slim_groups
    return stripped if isinstance(stripped, dict) else {}


def _whitelist_scenario(s: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "scenario_id",
        "scenario_type",
        "status",
        "scope_type",
        "scope_key",
    )
    return {k: s.get(k) for k in keys if k in s}


def _whitelist_pivot(p: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "pivot_id",
        "pivot_type",
        "scope_type",
        "scope_key",
        "suppressed_by",
    )
    return {k: p.get(k) for k in keys if k in p}


def _whitelist_canonical_summary(cs: Dict[str, Any]) -> Dict[str, Any]:
    """Only fixed-schema summary fields; strip everything else after deep strip."""
    allowed = frozenset(
        {
            "summary_version",
            "account_fingerprint_count",
            "bureau_codes",
            "negative_flag_count",
            "digest",
            "labels",
        }
    )
    base = {k: cs[k] for k in allowed if k in cs}
    return _strip_dict(base) if isinstance(_strip_dict(base), dict) else {}


def build_sanitized_model_payload(raw_request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Drop unknown top-level keys and nested disallowed fields.
    """
    req = {k: v for k, v in raw_request.items() if k in ALLOWED_REQUEST_TOP_LEVEL}
    out: Dict[str, Any] = {
        "workflow_id": str(req.get("workflow_id") or ""),
        "evaluation_run_id": str(req.get("evaluation_run_id") or ""),
        "output_category": str(req.get("output_category") or ""),
        "created_at": str(req.get("created_at") or ""),
    }
    gv = req.get("guidance_view")
    if isinstance(gv, dict):
        out["guidance_view"] = _whitelist_guidance_view(gv)
    scenarios = req.get("scenarios")
    if isinstance(scenarios, list):
        out["scenarios"] = [
            _whitelist_scenario(x) for x in scenarios if isinstance(x, dict)
        ]
    pivots = req.get("pivots")
    if isinstance(pivots, list):
        out["pivots"] = [_whitelist_pivot(x) for x in pivots if isinstance(x, dict)]
    cs = req.get("canonical_summary")
    if isinstance(cs, dict):
        out["canonical_summary"] = _whitelist_canonical_summary(cs)
    cleaned = _strip_dict(out)
    return cleaned if isinstance(cleaned, dict) else {}


def compute_ai_input_digest(sanitized_payload: Dict[str, Any]) -> str:
    canon = json.dumps(sanitized_payload, sort_keys=True, separators=(",", ":"), default=str)
    h = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    return f"sha256:{h}"


def build_ai_augmentation_request(
    *,
    workflow_id: str,
    evaluation_run_id: str,
    output_category: str,
    guidance_view: Optional[Dict[str, Any]] = None,
    scenarios: Optional[List[Dict[str, Any]]] = None,
    pivots: Optional[List[Dict[str, Any]]] = None,
    canonical_summary: Optional[Dict[str, Any]] = None,
    created_at: str = "",
    extra_forbidden_top_level: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build envelope. Unknown / forbidden top-level keys are ignored.
    `extra_forbidden_top_level` is used only in tests to simulate pollution.
    """
    raw: Dict[str, Any] = {
        "workflow_id": workflow_id,
        "evaluation_run_id": evaluation_run_id,
        "output_category": output_category,
        "created_at": created_at,
    }
    if guidance_view is not None:
        raw["guidance_view"] = guidance_view
    if scenarios is not None:
        raw["scenarios"] = scenarios
    if pivots is not None:
        raw["pivots"] = pivots
    if canonical_summary is not None:
        raw["canonical_summary"] = canonical_summary
    if extra_forbidden_top_level:
        raw.update(extra_forbidden_top_level)
    sanitized = build_sanitized_model_payload(raw)
    digest = compute_ai_input_digest(sanitized)
    return {
        "envelope_version": "ai_request@1.0.0",
        "sanitized_payload": sanitized,
        "input_digest": digest,
    }
