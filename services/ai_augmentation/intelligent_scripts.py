# AI augments execution language (scripts, talking points).
# AI must not change deterministic ORION decisions, actions, or workflow posture.
# ORION remains the source of truth for guidance, bestAction, explanations, and contracts.

"""
ORION V2.2 — Intelligent Script Layer (augmentation only).

Given deterministic ORION outputs, optionally produces short grounded scripts to help the user
execute the next step in their own words. Not a planner; does not persist by default.

ORION V2.3B — Proof customer scripts are execution-focused: compact, action-shaped, and
suppressed when redundant with deterministic or optional AI explanation text.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any, Dict, List, Literal, Mapping, Optional, Protocol, Tuple

from services.ai_augmentation.intelligent_explanation import (
    _orion_slice_from_workflow_api_payload,
    contract_completeness_from_orion_bundle,
)

_log = logging.getLogger(__name__)

INTELLIGENT_SCRIPT_FAMILY = "orion_intelligent_script_v1"

ScriptIntent = Literal[
    "proof_submission_support",
    "creditor_call_script",
    "bureau_contact_talking_points",
]

ScriptAugmentationStatus = Literal[
    "available",
    "unavailable",
    "skipped",
    "failed",
    "suppressed_ungrounded",
    "suppressed_redundant",
    "suppressed_too_long",
    "suppressed_not_action_shaped",
]

ProofScriptRefinementStatus = Literal[
    "accepted",
    "suppressed_redundant",
    "suppressed_too_long",
    "suppressed_not_action_shaped",
    "suppressed_ungrounded",
    "not_applicable",
]

PROOF_SCRIPT_MAX_LINES = 4
PROOF_SCRIPT_MAX_TALKING_POINTS = 4
_PROOF_MAX_INTRO_CHARS = 220
_PROOF_MAX_UNIT_CHARS = 180
_PROOF_MAX_TOTAL_BODY_CHARS = 900
_PROOF_MAX_LINES_PLUS_TP = 6

_ACTION_WORD_RE = re.compile(
    r"\b(upload|uploading|uploads|add|save|saved|sign|signature|signing|attach|submit|"
    r"complete|completed|click|continue|photo|pdf|file|files|document|documents|"
    r"\bid\b|address|done|ready|below|screen|cards?|snap|scan|clear|form|when|now|"
    r"right\s+here|this\s+step)\b",
    re.IGNORECASE,
)

ScriptTone = Literal["clear", "supportive", "firm", "calm"]

ALLOWED_SCRIPT_INTENTS: Tuple[str, ...] = (
    "proof_submission_support",
    "creditor_call_script",
    "bureau_contact_talking_points",
)

_MAX_JSON_CHARS = 12_000
_MAX_LIST_ITEMS = 24
_MAX_LINES = 8
_MAX_TALKING_POINTS = 6
_MAX_LINE_TEXT = 500
_MAX_TITLE = 200
_MAX_INTRO = 800


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
            slim_l = [
                _slim_dict(x, depth=depth + 1, max_depth=max_depth) if isinstance(x, dict) else x
                for x in v[:_MAX_LIST_ITEMS]
            ]
            out[str(k)] = slim_l + (["…"] if len(v) > _MAX_LIST_ITEMS else [])
        else:
            out[str(k)] = v
    return out


def build_intelligent_script_input(
    orion_bundle: Mapping[str, Any],
    *,
    workflow_id: str,
    script_intent: str,
    contract_completeness: str,
    current_step_id: Optional[str] = None,
    workflow_type: Optional[str] = None,
    page_surface: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compact, grounded input for script generation only.
    No event history; no case dumps — ORION slices only, slimmed for prompts.
    """
    wf = (workflow_id or "").strip()
    si = (script_intent or "").strip()
    cc_raw = (contract_completeness or "").strip()
    if cc_raw in ("full", "partial", "legacy"):
        cc: Literal["full", "partial", "legacy"] = cc_raw  # type: ignore[assignment]
    else:
        cc = contract_completeness_from_orion_bundle(orion_bundle)

    def pick(key: str) -> Any:
        v = orion_bundle.get(key)
        return _slim_dict(v) if isinstance(v, dict) else copy.deepcopy(v)

    out: Dict[str, Any] = {
        "workflowId": wf,
        "scriptIntent": si,
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
        "intelligentScriptFamily": INTELLIGENT_SCRIPT_FAMILY,
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


def _proof_submission_support_system_prompt(intent: str) -> str:
    return f"""You are a UX writing assistant for a credit-dispute program.

The JSON in the user message is authoritative ORION output (deterministic). scriptIntent is
"{intent}" — the user is on the **proof upload / signature screen**, not on a phone call.

Your job: produce **execution support** so they can do this step *now* — calm, scannable, and
**not** a third paraphrase of ORION's explanation.

Prioritize (pick what fits; stay brief):
- What they are doing on **this screen** right now (uploads + signature).
- What "done" looks like before they leave this page.
- Normalize the step (common, expected for certified-mail prep).
- One short phrase they could use **if someone asks what this is for** (optional).

Hard limits for this intent:
- At most **one** short intro (≤ ~2 sentences) or null.
- At most **4** lines (speaker "user" only) **and** at most **4** talking points total across both arrays;
  prefer **2–4** items in **one** of the two if that stays clearer.
- Each line or talking point: short (roughly one breath). No paragraphs.

Tone: calming, practical, plain language.

Explicitly FORBIDDEN:
- Restating bestActionExplanation.summary or whyNow in different words (do not repeat that narrative).
- Echoing hero/subtitle-style "what this step is" if it only duplicates explanation text.
- Phone-call scripts, creditor/bureau call language, or legal lectures.
- Long process summaries, timelines, or promises ORION did not state.
- Telling them to do a different next action than ORION's bestAction.

Output a single JSON object with keys:
- scriptIntent (string, must be "{intent}")
- title (string; compact, e.g. what they're doing now)
- intro (string or null)
- lines (array of {{ "speaker": "user", "text": string }})
- talkingPoints (array of strings)
- tone (one of: clear, supportive, firm, calm)
- groundedIn (object with bestActionKey, explanationType, guidanceType — mirror ORION, strings or null)

Forbidden: changing the recommended action, implying mail already sent, presenting as legal advice."""


def build_intelligent_script_prompt_messages(
    inp: Mapping[str, Any],
) -> Tuple[str, str]:
    """Grounded system + user messages for a model call."""
    intent = str(inp.get("scriptIntent") or "").strip()
    if intent == "proof_submission_support":
        system = _proof_submission_support_system_prompt(intent)
    else:
        system = f"""You are a UX writing assistant for a credit-dispute program.

The JSON in the user message is authoritative ORION output (deterministic). Your job is ONLY to
produce execution language for scriptIntent "{intent}".

Rules:
- Generate only the requested script intent; stay aligned with bestAction, bestActionExplanation, and guidance.
- Do not choose a different next action, imply new eligibility, or change workflow posture.
- Do not invent facts, timelines, promises, legal conclusions, or system states not present in ORION.
- Do not tell the user to do something ORION did not indicate (no extra steps, no unsupported escalation).
- Keep output concise and usable: short intro (optional), about 3–8 user lines (speaker "user" only), 3–6 talking points.
- Avoid aggressive legal positioning; do not present the script as legal advice from the system.

Output a single JSON object with keys:
- scriptIntent (string, must be "{intent}")
- title (string)
- intro (string or null)
- lines (array of objects with speaker "user" and text string)
- talkingPoints (array of strings)
- tone (one of: clear, supportive, firm, calm)
- groundedIn (object with bestActionKey, explanationType, guidanceType — each string or null, mirror ORION)

Forbidden: changing the recommended action, inventing bureau/creditor outcomes, implying letters were mailed when ORION does not say so, speaking as the company lawyer."""

    user = "Ground truth ORION payload (do not contradict):\n" + _truncate_for_prompt(dict(inp))
    return system, user


class IntelligentScriptBackend(Protocol):
    """Optional backend: returns inner aiScript dict or None."""

    def complete_json(self, *, system: str, user: str) -> Optional[Dict[str, Any]]:
        ...


def _explanation_type(orion_bundle: Mapping[str, Any]) -> str:
    expl = orion_bundle.get("bestActionExplanation")
    if not isinstance(expl, dict):
        return ""
    return str(expl.get("explanationType") or "").strip().lower()


def _intent_allowed_for_orion_posture(script_intent: str, orion_bundle: Mapping[str, Any]) -> bool:
    """Conservative gate before generation: skip action-oriented scripts when ORION is passive."""
    et = _explanation_type(orion_bundle)
    if script_intent == "proof_submission_support":
        return True
    if et in ("waiting", "blocked"):
        return False
    return True


def _stub_grounded_in(orion_bundle: Mapping[str, Any]) -> Dict[str, Optional[str]]:
    ba = orion_bundle.get("bestAction") if isinstance(orion_bundle.get("bestAction"), dict) else {}
    expl = (
        orion_bundle.get("bestActionExplanation")
        if isinstance(orion_bundle.get("bestActionExplanation"), dict)
        else {}
    )
    g = orion_bundle.get("guidance") if isinstance(orion_bundle.get("guidance"), dict) else None
    return {
        "bestActionKey": (str(ba.get("actionKey")).strip() or None) if ba.get("actionKey") else None,
        "explanationType": (str(expl.get("explanationType")).strip() or None)
        if expl.get("explanationType")
        else None,
        "guidanceType": (str(g.get("type")).strip() or None) if g and g.get("type") else None,
    }


def _stub_tone_from_orion(orion_bundle: Mapping[str, Any]) -> ScriptTone:
    et = _explanation_type(orion_bundle)
    if et == "warning":
        return "firm"
    if et == "waiting":
        return "calm"
    return "supportive"


def stub_complete_script_from_orion_input(
    inp: Mapping[str, Any],
    *,
    orion_bundle: Mapping[str, Any],
) -> Dict[str, Any]:
    """Deterministic short script from ORION slices only (no model)."""
    intent = str(inp.get("scriptIntent") or "").strip()
    ba = orion_bundle.get("bestAction") if isinstance(orion_bundle.get("bestAction"), dict) else {}
    expl = (
        orion_bundle.get("bestActionExplanation")
        if isinstance(orion_bundle.get("bestActionExplanation"), dict)
        else {}
    )
    label = str(ba.get("label") or "").strip() or "this step"
    summary = str(expl.get("summary") or "").strip()
    why = str(expl.get("whyNow") or "").strip()
    action_key = str(ba.get("actionKey") or "").strip()

    grounded = _stub_grounded_in(orion_bundle)
    tone = _stub_tone_from_orion(orion_bundle)

    if intent == "proof_submission_support":
        # V2.3B: execution-first — do not concatenate summary/why (duplicates deterministic explanation).
        title = "What you're doing right now"
        intro = (
            "Use the two upload areas below, then add your signature. "
            "This only prepares your package—nothing is mailed until you confirm on a later screen."
        )[:_PROOF_MAX_INTRO_CHARS]
        lines = [
            {
                "speaker": "user",
                "text": (
                    "I'm uploading my government ID and proof of address here, then signing—"
                    "whatever this screen asks for, nothing extra."
                )[:_MAX_LINE_TEXT],
            },
            {
                "speaker": "user",
                "text": (
                    "If someone asks what it's for: I'm matching my name and mailing address to the "
                    "certified mailing package for this dispute round."
                )[:_MAX_LINE_TEXT],
            },
        ]
        tp = [
            "Done means both documents saved on file and your signature saved—then Continue when it turns on.",
            "Blurry files get rejected; a clear photo or PDF of each item is enough.",
        ]

    elif intent == "creditor_call_script":
        title = f"Call script — {label}"
        intro = (summary[:300] + (" " + why[:300] if why else "")).strip()[:_MAX_INTRO] or None
        lines = [
            {"speaker": "user", "text": f"Hi, I'm calling about my account related to: {label}."[:_MAX_LINE_TEXT]},
            {
                "speaker": "user",
                "text": "I'm following the steps in my dispute program and want to request written verification of what you're reporting, if that's appropriate for my situation."
                [:_MAX_LINE_TEXT],
            },
            {
                "speaker": "user",
                "text": "Can you note what I need to send or where I should direct written correspondence?"
                [:_MAX_LINE_TEXT],
            },
        ]
        tp = [
            "Stay calm; ask for clarity on what they need from you.",
            "Do not claim legal outcomes — ask for process and documentation paths.",
            "If the call isn't productive, follow the next ORION step instead of arguing.",
        ][: _MAX_TALKING_POINTS]

    elif intent == "bureau_contact_talking_points":
        title = "Bureau contact — talking points"
        intro = None
        lines = [
            {
                "speaker": "user",
                "text": f"I'm contacting you about items on my report related to: {label}."
                [:_MAX_LINE_TEXT],
            },
            {
                "speaker": "user",
                "text": "I'm disputing inaccurate or incomplete information and can provide supporting details as required."
                [:_MAX_LINE_TEXT],
            },
        ]
        tp = [
            "Reference the specific tradeline or item as shown on your report copy.",
            "Ask what format they prefer for disputes and supporting documents.",
            "Keep requests factual; avoid definitive legal conclusions.",
            "Follow the next ORION step for letters or mailing if that is what your program shows.",
        ][: _MAX_TALKING_POINTS]

    else:
        raise ValueError(f"unsupported script intent for stub: {intent!r}")

    return {
        "scriptIntent": intent,
        "title": title[:_MAX_TITLE],
        "intro": intro,
        "lines": lines[:_MAX_LINES],
        "talkingPoints": [p[:_MAX_LINE_TEXT] for p in tp][: _MAX_TALKING_POINTS],
        "tone": tone,
        "groundedIn": grounded,
    }


def _validate_ai_script_shape(obj: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return None
    intent = str(obj.get("scriptIntent") or "").strip()
    if intent not in ALLOWED_SCRIPT_INTENTS:
        return None
    if not isinstance(obj.get("title"), str) or not str(obj.get("title")).strip():
        return None
    intro = obj.get("intro")
    if intro is not None and not isinstance(intro, str):
        return None
    tone = obj.get("tone")
    if tone not in ("clear", "supportive", "firm", "calm"):
        return None
    lines = obj.get("lines")
    if not isinstance(lines, list) or len(lines) > _MAX_LINES:
        return None
    out_lines: List[Dict[str, str]] = []
    for row in lines:
        if not isinstance(row, dict):
            return None
        if row.get("speaker") != "user":
            return None
        t = row.get("text")
        if not isinstance(t, str) or not t.strip():
            return None
        out_lines.append({"speaker": "user", "text": t.strip()[:_MAX_LINE_TEXT]})
    tps = obj.get("talkingPoints")
    if not isinstance(tps, list) or len(tps) > _MAX_TALKING_POINTS:
        return None
    out_tp: List[str] = []
    for p in tps:
        if not isinstance(p, str) or not p.strip():
            return None
        out_tp.append(p.strip()[:_MAX_LINE_TEXT])
    gi = obj.get("groundedIn")
    if not isinstance(gi, dict):
        return None
    for k in ("bestActionKey", "explanationType", "guidanceType"):
        v = gi.get(k)
        if v is not None and not isinstance(v, str):
            return None

    return {
        "scriptIntent": intent,
        "title": str(obj["title"]).strip()[:_MAX_TITLE],
        "intro": (str(intro).strip()[:_MAX_INTRO] if intro is not None else None),
        "lines": out_lines,
        "talkingPoints": out_tp,
        "tone": tone,
        "groundedIn": {
            "bestActionKey": gi.get("bestActionKey"),
            "explanationType": gi.get("explanationType"),
            "guidanceType": gi.get("guidanceType"),
        },
    }


def validate_customer_ai_script_against_orion(
    ai_script: Optional[Dict[str, Any]],
    orion_bundle: Mapping[str, Any],
    *,
    script_intent: str,
) -> Optional[Dict[str, Any]]:
    """
    Customer-safe guard: drop script if shape is wrong, intent mismatches, conflicts with ORION,
    or posture disallows this script type.
    """
    if not ai_script or not isinstance(ai_script, dict):
        return None
    validated = _validate_ai_script_shape(ai_script)
    if validated is None:
        return None
    if validated.get("scriptIntent") != (script_intent or "").strip():
        return None

    if not _intent_allowed_for_orion_posture(script_intent, orion_bundle):
        return None

    det_ba = orion_bundle.get("bestAction")
    det_key = str(det_ba.get("actionKey") or "").strip() if isinstance(det_ba, dict) else ""
    gi = validated.get("groundedIn") or {}
    ai_key_raw = gi.get("bestActionKey")
    ai_key = str(ai_key_raw).strip() if ai_key_raw is not None else ""
    if det_key and ai_key and ai_key != det_key:
        return None

    return validated


def _tokenize_words(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9']+", text.lower()) if len(t) > 2]


def _proof_redundancy_corpus(
    orion_bundle: Mapping[str, Any],
    ai_explanation: Any,
) -> str:
    chunks: List[str] = []
    expl = orion_bundle.get("bestActionExplanation")
    if isinstance(expl, dict):
        chunks.append(str(expl.get("summary") or ""))
        chunks.append(str(expl.get("whyNow") or ""))
    if isinstance(ai_explanation, dict):
        chunks.append(str(ai_explanation.get("headline") or ""))
        chunks.append(str(ai_explanation.get("body") or ""))
    return " ".join(chunks)


def _proof_script_flat_text(script: Mapping[str, Any]) -> str:
    parts: List[str] = [
        str(script.get("title") or ""),
        str(script.get("intro") or ""),
    ]
    for row in script.get("lines") or []:
        if isinstance(row, dict):
            parts.append(str(row.get("text") or ""))
    for p in script.get("talkingPoints") or []:
        if isinstance(p, str):
            parts.append(p)
    return " ".join(parts)


def assess_proof_script_distinctiveness(
    script: Mapping[str, Any],
    orion_bundle: Mapping[str, Any],
    *,
    ai_explanation: Any = None,
) -> ProofScriptRefinementStatus:
    """
    Lightweight anti-redundancy / execution-shape gate for proof_submission_support only.
    Not semantic NLP — token overlap, length budgets, and action-word heuristics.
    """
    lines = script.get("lines") if isinstance(script.get("lines"), list) else []
    tps = script.get("talkingPoints") if isinstance(script.get("talkingPoints"), list) else []
    if len(lines) > PROOF_SCRIPT_MAX_LINES or len(tps) > PROOF_SCRIPT_MAX_TALKING_POINTS:
        return "suppressed_too_long"
    if len(lines) + len(tps) > _PROOF_MAX_LINES_PLUS_TP:
        return "suppressed_too_long"
    intro = script.get("intro")
    if isinstance(intro, str) and len(intro) > _PROOF_MAX_INTRO_CHARS:
        return "suppressed_too_long"

    flat = _proof_script_flat_text(script)
    if len(flat) > _PROOF_MAX_TOTAL_BODY_CHARS:
        return "suppressed_too_long"

    for row in lines:
        if isinstance(row, dict) and len(str(row.get("text") or "")) > _PROOF_MAX_UNIT_CHARS:
            return "suppressed_too_long"
    for p in tps:
        if isinstance(p, str) and len(p) > _PROOF_MAX_UNIT_CHARS:
            return "suppressed_too_long"

    if len(lines) + len(tps) < 1:
        return "suppressed_not_action_shaped"

    if len(_ACTION_WORD_RE.findall(flat)) < 2:
        return "suppressed_not_action_shaped"

    corp = _proof_redundancy_corpus(orion_bundle, ai_explanation)
    corp_toks = set(_tokenize_words(corp))
    script_toks = _tokenize_words(flat)
    if len(script_toks) >= 10:
        overlap = sum(1 for t in script_toks if t in corp_toks) / max(len(script_toks), 1)
        if overlap > 0.52:
            return "suppressed_redundant"

    if isinstance(intro, str) and intro.strip():
        iw = _tokenize_words(intro)
        if len(iw) >= 6:
            io = sum(1 for t in iw if t in corp_toks) / len(iw)
            if io > 0.62:
                return "suppressed_redundant"

    return "accepted"


def refine_proof_submission_script_for_customer(
    script: Dict[str, Any],
    orion_bundle: Mapping[str, Any],
    ai_explanation: Any,
) -> Tuple[Optional[Dict[str, Any]], ProofScriptRefinementStatus]:
    """Apply V2.3B refinement after grounding validation; returns None if script should not ship."""
    verdict = assess_proof_script_distinctiveness(script, orion_bundle, ai_explanation=ai_explanation)
    if verdict != "accepted":
        return None, verdict
    return copy.deepcopy(script), "accepted"


def generate_intelligent_script(
    *,
    orion_bundle: Mapping[str, Any],
    workflow_id: str,
    script_intent: str,
    contract_completeness: Optional[str] = None,
    current_step_id: Optional[str] = None,
    workflow_type: Optional[str] = None,
    page_surface: Optional[str] = None,
    invoke_ai: bool = False,
    backend: Optional[IntelligentScriptBackend] = None,
) -> Dict[str, Any]:
    """
    Read-only augmentation. Does not mutate ``orion_bundle``.

    - invoke_ai=False: scriptAugmentationStatus ``skipped``, aiScript null.
    - invoke_ai=True, backend=None: deterministic stub from ORION input.
    - invoke_ai=True, backend set: model JSON; invalid shape -> failed.
    """
    base: Dict[str, Any] = {
        "intelligentScriptFamily": INTELLIGENT_SCRIPT_FAMILY,
        "aiScript": None,
        "scriptAugmentationStatus": "skipped",
    }

    si = (script_intent or "").strip()
    if si not in ALLOWED_SCRIPT_INTENTS:
        base["scriptAugmentationStatus"] = "failed"
        return base

    cc = contract_completeness or contract_completeness_from_orion_bundle(orion_bundle)
    inp = build_intelligent_script_input(
        orion_bundle,
        workflow_id=workflow_id,
        script_intent=si,
        contract_completeness=cc,
        current_step_id=current_step_id,
        workflow_type=workflow_type,
        page_surface=page_surface,
    )

    if not invoke_ai:
        base["scriptAugmentationStatus"] = "skipped"
        return base

    if not _intent_allowed_for_orion_posture(si, orion_bundle):
        base["scriptAugmentationStatus"] = "skipped"
        return base

    try:
        if backend is None:
            base["aiScript"] = stub_complete_script_from_orion_input(inp, orion_bundle=orion_bundle)
            base["scriptAugmentationStatus"] = "available"
            return base

        system, user = build_intelligent_script_prompt_messages(inp)
        raw = backend.complete_json(system=system, user=user)
        if raw is None:
            base["scriptAugmentationStatus"] = "unavailable"
            return base
        validated = _validate_ai_script_shape(raw)
        if validated is None:
            base["scriptAugmentationStatus"] = "failed"
            return base
        if validated.get("scriptIntent") != si:
            base["scriptAugmentationStatus"] = "failed"
            return base
        base["aiScript"] = validated
        base["scriptAugmentationStatus"] = "available"
        return base
    except Exception:
        _log.debug("generate_intelligent_script failed", exc_info=True)
        base["aiScript"] = None
        base["scriptAugmentationStatus"] = "failed"
        return base


PROOF_CUSTOMER_SCRIPT_INTENT = "proof_submission_support"


def _finalize_proof_submission_script_for_customer(
    orion_bundle: Mapping[str, Any],
    gen: Mapping[str, Any],
    *,
    ai_explanation: Any = None,
) -> Dict[str, Any]:
    """
    Grounding + V2.3B refinement on a ``generate_intelligent_script`` result for proof intent.
    Shared by customer merge and optional internal audit preview.
    """
    raw_ai = gen.get("aiScript")
    status = str(gen.get("scriptAugmentationStatus") or "skipped")
    family = str(gen.get("intelligentScriptFamily") or INTELLIGENT_SCRIPT_FAMILY)

    validated = validate_customer_ai_script_against_orion(
        raw_ai if isinstance(raw_ai, dict) else None,
        orion_bundle,
        script_intent=PROOF_CUSTOMER_SCRIPT_INTENT,
    )

    refinement_status: ProofScriptRefinementStatus = "not_applicable"

    if raw_ai is not None and validated is None:
        status = "suppressed_ungrounded"
        refinement_status = "suppressed_ungrounded"
    elif validated is not None:
        refined, ref_st = refine_proof_submission_script_for_customer(
            validated,
            orion_bundle,
            ai_explanation,
        )
        refinement_status = ref_st
        if refined is None:
            validated = None
            if ref_st == "suppressed_redundant":
                status = "suppressed_redundant"
            elif ref_st == "suppressed_too_long":
                status = "suppressed_too_long"
            elif ref_st == "suppressed_not_action_shaped":
                status = "suppressed_not_action_shaped"
            else:
                status = "suppressed_ungrounded"
        else:
            validated = refined
            status = "available"
    else:
        refinement_status = "not_applicable"

    return {
        "aiScript": validated,
        "scriptAugmentationStatus": status,
        "intelligentScriptFamily": family,
        "proofScriptRefinementStatus": refinement_status,
    }


def merge_customer_workflow_payload_with_proof_ai_script(
    *,
    payload: Dict[str, Any],
    workflow_id: str,
    include_ai_script: bool,
) -> Dict[str, Any]:
    """
    Additive customer fields for proof context only when ``include_ai_script`` is true.

    Always uses ``proof_submission_support`` only. Does not mutate ``payload``.
    """
    if not include_ai_script:
        return {}

    wf = (workflow_id or "").strip()
    orion_slice = _orion_slice_from_workflow_api_payload(payload)
    cc = contract_completeness_from_orion_bundle(orion_slice)

    gen = generate_intelligent_script(
        orion_bundle=orion_slice,
        workflow_id=wf,
        script_intent=PROOF_CUSTOMER_SCRIPT_INTENT,
        contract_completeness=cc,
        current_step_id="proof_attachment",
        page_surface="proof_attachment",
        invoke_ai=True,
        backend=None,
    )
    return _finalize_proof_submission_script_for_customer(
        orion_slice,
        gen,
        ai_explanation=payload.get("aiExplanation"),
    )


def internal_intelligent_script_audit(
    workflow_id: str,
    script_intent: str,
    *,
    invoke_ai: bool = True,
    persist_guidance: bool = False,
    apply_refinement: bool = False,
) -> Dict[str, Any]:
    """
    Operator/debug: ORION bundle + script augmentation. Read-only for workflow state
    aside from optional guidance persistence matching ``customer_orion_bundle_for_api``.

    When ``apply_refinement`` is true and ``script_intent`` is ``proof_submission_support``,
    adds ``proofCustomerPreview``: same grounding + distinctiveness pipeline as the proof
    context customer path (``aiExplanation`` not modeled here — pass ``None`` for overlap checks).
    Raw ``augmentation`` from ``generate_intelligent_script`` is always unchanged.
    """
    from services.guidance.guidance_engine import customer_orion_bundle_for_api

    wf = (workflow_id or "").strip()
    si = (script_intent or "").strip()
    bundle = customer_orion_bundle_for_api(wf if wf else None, persist_guidance=persist_guidance)
    cc = contract_completeness_from_orion_bundle(bundle)
    inp = build_intelligent_script_input(
        bundle,
        workflow_id=wf,
        script_intent=si,
        contract_completeness=cc,
    )
    aug = generate_intelligent_script(
        orion_bundle=bundle,
        workflow_id=wf,
        script_intent=si,
        contract_completeness=cc,
        invoke_ai=invoke_ai,
        backend=None,
    )
    out: Dict[str, Any] = {
        "workflowId": wf or None,
        "scriptIntent": si,
        "contractCompleteness": cc,
        "input": inp,
        "augmentation": aug,
        "orionEcho": {
            "bestAction": bundle.get("bestAction"),
            "bestActionExplanation": bundle.get("bestActionExplanation"),
        },
    }
    if apply_refinement and si == PROOF_CUSTOMER_SCRIPT_INTENT:
        out["proofCustomerPreview"] = _finalize_proof_submission_script_for_customer(
            bundle,
            aug,
            ai_explanation=None,
        )
    return out
