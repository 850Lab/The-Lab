# AI augments ORION explanation.
# AI must not change deterministic ORION decisions.
# ORION remains the source of truth for action, priority, and workflow posture.

"""
ORION V2.1 — Intelligent Explanation Layer (augmentation only).

Reads deterministic ORION customer-bundle fields and optionally produces richer wording.
Never mutates ORION outputs; failures yield null aiExplanation and a non-throwing status.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, Dict, List, Literal, Mapping, Optional, Protocol, Tuple

_log = logging.getLogger(__name__)

INTELLIGENT_EXPLANATION_FAMILY = "orion_intelligent_explanation_v1"

AugmentationStatus = Literal[
    "available",
    "unavailable",
    "skipped",
    "failed",
    "suppressed_ungrounded",
]
ContractCompleteness = Literal["full", "partial", "legacy"]
Tone = Literal["supportive", "urgent", "calm", "clear"]

_MAX_JSON_CHARS = 12_000
_MAX_LIST_ITEMS = 24


def _truncate_for_prompt(obj: Any, *, max_chars: int = _MAX_JSON_CHARS) -> str:
    raw = json.dumps(obj, default=str, ensure_ascii=False, separators=(",", ":"))
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars] + "…"


def _slim_dict(d: Mapping[str, Any], *, depth: int = 0, max_depth: int = 4) -> Dict[str, Any]:
    if depth > max_depth or not isinstance(d, Mapping):
        return {}
    out: Dict[str, Any] = {}
    for i, (k, v) in enumerate(d.items()):
        if i >= 40:
            out["_omitted_keys"] = True
            break
        if isinstance(v, dict):
            out[str(k)] = _slim_dict(v, depth=depth + 1, max_depth=max_depth)
        elif isinstance(v, list):
            out[str(k)] = [
                _slim_dict(x, depth=depth + 1, max_depth=max_depth) if isinstance(x, dict) else x
                for x in v[:_MAX_LIST_ITEMS]
            ]
            if len(v) > _MAX_LIST_ITEMS:
                out[str(k)] = out[str(k)] + ["…"]
        else:
            out[str(k)] = v
    return out


def contract_completeness_from_orion_bundle(bundle: Mapping[str, Any]) -> ContractCompleteness:
    """Mirror frontend coarse completeness from a customer ORION bundle (no workflow DB reads)."""
    dp = bundle.get("deliveryPrioritization")
    ux = bundle.get("uxSurfaceContract")
    if (
        isinstance(dp, dict)
        and isinstance(ux, dict)
        and isinstance(dp.get("primaryFocus"), dict)
        and isinstance(ux.get("primarySurface"), dict)
    ):
        return "full"
    if (
        bundle.get("guidance") is not None
        or bundle.get("bestAction") is not None
        or bundle.get("bestActionExplanation") is not None
    ):
        return "partial"
    ac = bundle.get("actionCandidates")
    if isinstance(ac, list) and len(ac) > 0:
        return "partial"
    return "legacy"


def build_intelligent_explanation_input(
    orion_bundle: Mapping[str, Any],
    *,
    workflow_id: str,
    contract_completeness: str,
    current_step_id: Optional[str] = None,
    workflow_type: Optional[str] = None,
    page_surface: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compact, grounded input for the intelligent explanation layer only.
    No event history; ORION fragments are slimmed for prompt safety.
    """
    wf = (workflow_id or "").strip()
    cc: ContractCompleteness
    if contract_completeness in ("full", "partial", "legacy"):
        cc = contract_completeness  # type: ignore[assignment]
    else:
        cc = contract_completeness_from_orion_bundle(orion_bundle)

    def pick(key: str) -> Any:
        v = orion_bundle.get(key)
        return _slim_dict(v) if isinstance(v, dict) else copy.deepcopy(v)

    out: Dict[str, Any] = {
        "workflowId": wf,
        "bestAction": pick("bestAction"),
        "bestActionExplanation": pick("bestActionExplanation"),
        "guidance": pick("guidance") if orion_bundle.get("guidance") is not None else None,
        "deliveryPrioritization": pick("deliveryPrioritization")
        if orion_bundle.get("deliveryPrioritization") is not None
        else None,
        "uxSurfaceContract": pick("uxSurfaceContract")
        if orion_bundle.get("uxSurfaceContract") is not None
        else None,
        "contractCompleteness": cc,
        "intelligentExplanationFamily": INTELLIGENT_EXPLANATION_FAMILY,
    }
    meta: Dict[str, Any] = {}
    if current_step_id:
        meta["currentStepId"] = str(current_step_id)[:128]
    if workflow_type:
        meta["workflowType"] = str(workflow_type)[:128]
    if page_surface:
        meta["pageSurface"] = str(page_surface)[:128]
    if meta:
        out["contextMetadata"] = meta
    return out


def build_intelligent_explanation_prompt_messages(
    inp: Mapping[str, Any],
) -> Tuple[str, str]:
    """
    System + user messages for a grounded model call.
    Instructs the model to paraphrase ORION only; forbid new actions or states.
    """
    system = """You are a UX writing assistant for a credit-dispute program.

The JSON in the user message is the authoritative ORION system output (deterministic).
Your job: produce clearer, supportive user-facing wording ONLY.

Rules:
- Stay consistent with bestAction and bestActionExplanation; do not change the recommended action or priority.
- Do not introduce new steps, timelines, promises, legal claims, or system states.
- Do not contradict requirement, waiting, warning, or blocked posture implied by ORION.
- Do not invent facts; if information is missing, stay general and honest.
- Output a single JSON object with keys: headline (string), body (string), nextStepLabel (string or null), tone (one of: supportive, urgent, calm, clear).
- nextStepLabel should mirror the user's next action label from ORION when present, not a new instruction.

Forbidden: changing actionKey, suggesting escalation not present in ORION, implying a blocked step is ready."""

    user = (
        "Ground truth ORION payload (do not contradict):\n"
        + _truncate_for_prompt(dict(inp))
    )
    return system, user


class IntelligentExplanationBackend(Protocol):
    """Optional backend: returns inner aiExplanation dict or None on failure."""

    def complete_json(self, *, system: str, user: str) -> Optional[Dict[str, Any]]:
        ...


def _tone_from_explanation(expl: Mapping[str, Any]) -> Tone:
    et = str(expl.get("explanationType") or "").lower()
    if et == "warning":
        return "urgent"
    if et == "waiting":
        return "calm"
    if et == "requirement":
        return "clear"
    return "supportive"


def stub_complete_from_orion_input(inp: Mapping[str, Any]) -> Dict[str, Any]:
    """Build aiExplanation object from ORION slices only (deterministic stub)."""
    ba = inp.get("bestAction") if isinstance(inp.get("bestAction"), dict) else {}
    expl = inp.get("bestActionExplanation") if isinstance(inp.get("bestActionExplanation"), dict) else {}
    g = inp.get("guidance") if isinstance(inp.get("guidance"), dict) else None

    headline = (
        str(ba.get("label") or expl.get("summary") or "Continue in your program")[:200]
    )
    parts: List[str] = []
    if expl.get("summary"):
        parts.append(str(expl.get("summary")))
    if expl.get("whyNow"):
        parts.append(str(expl.get("whyNow")))
    if not parts and g and g.get("message"):
        parts.append(str(g.get("message")))
    body = " ".join(parts)[:1200] if parts else "Follow the recommended step shown in your program."
    next_label = str(ba.get("label") or "")[:120] or None
    action_key = str(ba.get("actionKey") or "") or None

    return {
        "headline": headline,
        "body": body,
        "nextStepLabel": next_label,
        "tone": _tone_from_explanation(expl),
        "groundedIn": {
            "bestActionKey": action_key,
            "explanationType": str(expl.get("explanationType") or "") or None,
            "guidanceType": str(g.get("type") or "") if g else None,
        },
    }


def _validate_ai_explanation_shape(obj: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return None
    if not isinstance(obj.get("headline"), str) or not isinstance(obj.get("body"), str):
        return None
    tone = obj.get("tone")
    if tone not in ("supportive", "urgent", "calm", "clear"):
        return None
    nsl = obj.get("nextStepLabel")
    if nsl is not None and not isinstance(nsl, str):
        return None
    gi = obj.get("groundedIn")
    if not isinstance(gi, dict):
        return None
    for k in ("bestActionKey", "explanationType", "guidanceType"):
        v = gi.get(k)
        if v is not None and not isinstance(v, str):
            return None
    return {
        "headline": obj["headline"][:2000],
        "body": obj["body"][:8000],
        "nextStepLabel": (str(nsl)[:500] if nsl else None),
        "tone": tone,
        "groundedIn": {
            "bestActionKey": gi.get("bestActionKey"),
            "explanationType": gi.get("explanationType"),
            "guidanceType": gi.get("guidanceType"),
        },
    }


def generate_intelligent_explanation(
    *,
    orion_bundle: Mapping[str, Any],
    workflow_id: str,
    contract_completeness: Optional[str] = None,
    current_step_id: Optional[str] = None,
    workflow_type: Optional[str] = None,
    page_surface: Optional[str] = None,
    invoke_ai: bool = False,
    backend: Optional[IntelligentExplanationBackend] = None,
) -> Dict[str, Any]:
    """
    Read-only augmentation. Does not mutate ``orion_bundle``.

    - invoke_ai=False: augmentationStatus ``skipped`` (default; no model call).
    - invoke_ai=True, backend=None: uses deterministic stub derived from ORION input.
    - invoke_ai=True, backend set: calls ``complete_json``; on None/invalid shape -> failed.
    """
    base: Dict[str, Any] = {
        "intelligentExplanationFamily": INTELLIGENT_EXPLANATION_FAMILY,
        "aiExplanation": None,
        "augmentationStatus": "skipped",
    }

    cc = contract_completeness or contract_completeness_from_orion_bundle(orion_bundle)
    inp = build_intelligent_explanation_input(
        orion_bundle,
        workflow_id=workflow_id,
        contract_completeness=cc,
        current_step_id=current_step_id,
        workflow_type=workflow_type,
        page_surface=page_surface,
    )

    if not invoke_ai:
        base["augmentationStatus"] = "skipped"
        return base

    try:
        if backend is None:
            base["aiExplanation"] = stub_complete_from_orion_input(inp)
            base["augmentationStatus"] = "available"
            return base

        system, user = build_intelligent_explanation_prompt_messages(inp)
        raw = backend.complete_json(system=system, user=user)
        if raw is None:
            base["augmentationStatus"] = "unavailable"
            return base
        validated = _validate_ai_explanation_shape(raw)
        if validated is None:
            base["augmentationStatus"] = "failed"
            return base
        base["aiExplanation"] = validated
        base["augmentationStatus"] = "available"
        return base
    except Exception:
        _log.debug("generate_intelligent_explanation failed", exc_info=True)
        base["aiExplanation"] = None
        base["augmentationStatus"] = "failed"
        return base


def _orion_slice_from_workflow_api_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Subset of customer workflow JSON used for intelligent explanation (read-only view)."""
    keys = (
        "guidance",
        "bestAction",
        "bestActionExplanation",
        "actionCandidates",
        "deliveryPrioritization",
        "uxSurfaceContract",
    )
    return {k: copy.deepcopy(payload.get(k)) for k in keys}


def validate_customer_ai_explanation_against_orion(
    ai_ex: Optional[Dict[str, Any]],
    orion_bundle: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Customer-safe guard: drop augmentation if it conflicts with deterministic ORION
    or fails lightweight posture checks.
    """
    if not ai_ex or not isinstance(ai_ex, dict):
        return None
    validated = _validate_ai_explanation_shape(ai_ex)
    if validated is None:
        return None

    det_ba = orion_bundle.get("bestAction")
    det_key = str(det_ba.get("actionKey") or "").strip() if isinstance(det_ba, dict) else ""
    gi = validated.get("groundedIn") or {}
    ai_key_raw = gi.get("bestActionKey")
    ai_key = str(ai_key_raw).strip() if ai_key_raw is not None else ""
    if det_key and ai_key and ai_key != det_key:
        return None

    det_expl = orion_bundle.get("bestActionExplanation")
    expl_type = (
        str(det_expl.get("explanationType") or "").strip().lower()
        if isinstance(det_expl, dict)
        else ""
    )
    tone = str(validated.get("tone") or "")
    if expl_type == "waiting" and tone == "urgent":
        return None
    if expl_type == "warning" and tone == "calm":
        return None

    return validated


def merge_customer_workflow_payload_with_proof_ai_explanation(
    *,
    payload: Dict[str, Any],
    workflow_id: str,
    include_ai_explanation: bool,
) -> Dict[str, Any]:
    """
    Additive customer fields for proof context only when ``include_ai_explanation`` is true.

    Does not mutate ``payload``. Returns only the extra keys to merge into the response.
    """
    if not include_ai_explanation:
        return {}

    wf = (workflow_id or "").strip()
    orion_slice = _orion_slice_from_workflow_api_payload(payload)
    gen = generate_intelligent_explanation(
        orion_bundle=orion_slice,
        workflow_id=wf,
        page_surface="proof_attachment",
        current_step_id="proof_attachment",
        invoke_ai=True,
        backend=None,
    )
    raw_ai = gen.get("aiExplanation")
    status = str(gen.get("augmentationStatus") or "skipped")
    family = str(gen.get("intelligentExplanationFamily") or INTELLIGENT_EXPLANATION_FAMILY)

    validated = validate_customer_ai_explanation_against_orion(
        raw_ai if isinstance(raw_ai, dict) else None,
        orion_slice,
    )
    if raw_ai is not None and validated is None:
        status = "suppressed_ungrounded"

    return {
        "aiExplanation": validated,
        "aiAugmentationStatus": status,
        "intelligentExplanationFamily": family,
    }


def internal_intelligent_explanation_audit(
    workflow_id: str,
    *,
    invoke_ai: bool = True,
    persist_guidance: bool = False,
) -> Dict[str, Any]:
    """
    Operator/debug: ORION bundle + augmentation result. Read-only for workflow state
    aside from optional guidance persistence matching customer_orion_bundle_for_api.
    """
    from services.guidance.guidance_engine import customer_orion_bundle_for_api

    wf = (workflow_id or "").strip()
    bundle = customer_orion_bundle_for_api(wf if wf else None, persist_guidance=persist_guidance)
    cc = contract_completeness_from_orion_bundle(bundle)
    result = generate_intelligent_explanation(
        orion_bundle=bundle,
        workflow_id=wf,
        contract_completeness=cc,
        invoke_ai=invoke_ai,
        backend=None,
    )
    return {
        "workflowId": wf or None,
        "contractCompleteness": cc,
        "input": build_intelligent_explanation_input(
            bundle,
            workflow_id=wf,
            contract_completeness=cc,
        ),
        "augmentation": result,
        # Echo ORION fields for audit diff; do not claim AI authority.
        "orionEcho": {
            "bestAction": bundle.get("bestAction"),
            "bestActionExplanation": bundle.get("bestActionExplanation"),
        },
    }
