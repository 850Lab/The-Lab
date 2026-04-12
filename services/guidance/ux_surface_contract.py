"""
O.R.I.O.N. V1.5 — deterministic UX surface intent contract (not UI, no AI).

Maps existing ORION bundle outputs to stable presentation metadata for clients.
Does not query workflow event history.

ORION is deterministic. Do NOT inject AI logic here. AI layers must consume ORION outputs, not modify them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

UX_SURFACE_CONTRACT_VERSION = "orion_ux_surface_contract_v1"

PrimarySurfaceType = Literal[
    "warning_banner",
    "hero_panel",
    "inline_card",
    "passive_status",
    "completion_status",
]
PrimaryAttention = Literal["dominant", "strong", "supportive", "quiet"]
RenderIntent = Literal[
    "warning",
    "progress",
    "waiting",
    "requirement",
    "review",
    "completion",
    "neutral",
]
PrimaryContentSource = Literal[
    "guidance",
    "best_action",
    "best_action_explanation",
    "status",
]
ActionPresentation = Literal[
    "primary_cta",
    "secondary_cta",
    "informational_only",
    "none",
]

SupportingSurfaceType = Literal[
    "inline_card",
    "passive_status",
    "support_strip",
    "candidate_list",
]
SupportingAttention = Literal["supportive", "quiet"]
SupportingContentSource = Literal[
    "guidance",
    "best_action",
    "best_action_explanation",
    "candidate_list",
    "status",
]


@dataclass
class PrimarySurface:
    surface_type: PrimarySurfaceType
    attention_level: PrimaryAttention
    render_intent: RenderIntent
    content_source: PrimaryContentSource
    action_presentation: ActionPresentation
    reason_code: str

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "surfaceType": self.surface_type,
            "attentionLevel": self.attention_level,
            "renderIntent": self.render_intent,
            "contentSource": self.content_source,
            "actionPresentation": self.action_presentation,
            "reasonCode": self.reason_code,
        }


@dataclass
class SupportingSurface:
    surface_type: SupportingSurfaceType
    attention_level: SupportingAttention
    render_intent: RenderIntent
    content_source: SupportingContentSource
    action_presentation: ActionPresentation
    reason_code: str

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "surfaceType": self.surface_type,
            "attentionLevel": self.attention_level,
            "renderIntent": self.render_intent,
            "contentSource": self.content_source,
            "actionPresentation": self.action_presentation,
            "reasonCode": self.reason_code,
        }


@dataclass
class UxSurfaceContract:
    primary_surface: PrimarySurface
    supporting_surfaces: List[SupportingSurface] = field(default_factory=list)
    surface_contract_version: str = UX_SURFACE_CONTRACT_VERSION

    def to_user_api_dict(self) -> Dict[str, Any]:
        return {
            "primarySurface": self.primary_surface.to_api_dict(),
            "supportingSurfaces": [s.to_api_dict() for s in self.supporting_surfaces],
            "surfaceContractVersion": self.surface_contract_version,
        }

    def to_audit_dict(self) -> Dict[str, Any]:
        return self.to_user_api_dict()


def _guidance_type(g: Optional[Dict[str, Any]]) -> str:
    if not g or not isinstance(g, dict):
        return ""
    return str(g.get("type") or "").strip()


def _best_key(ba: Optional[Dict[str, Any]]) -> str:
    if not ba or not isinstance(ba, dict):
        return ""
    return str(ba.get("actionKey") or "").strip()


def _expl_type(expl: Optional[Dict[str, Any]]) -> str:
    if not expl or not isinstance(expl, dict):
        return ""
    return str(expl.get("explanationType") or "").strip()


def _overall(ctx: Optional[Dict[str, Any]]) -> str:
    if not ctx or not isinstance(ctx, dict):
        return ""
    return str(ctx.get("overallStatus") or "").strip()


def _parse_dp(dp: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not dp or not isinstance(dp, dict):
        return {}, []
    pf = dp.get("primaryFocus")
    pf_d = pf if isinstance(pf, dict) else {}
    sec = dp.get("secondarySupport")
    sec_l = sec if isinstance(sec, list) else []
    return pf_d, [x for x in sec_l if isinstance(x, dict)]


REQUIREMENT_ACTION_KEYS = frozenset({"complete_payment", "upload_proof_documents"})
REVIEW_INLINE_ACTION_KEYS = frozenset(
    {
        "review_claims",
        "review_dispute_selection",
        "check_tracking_status",
        "review_escalation_options",
    }
)
HERO_PROGRESS_ACTION_KEYS = frozenset(
    {
        "resume_upload",
        "retry_upload",
        "review_generated_letters",
        "confirm_mail_step",
    }
)


def _render_intent_from_explanation(expl: Optional[Dict[str, Any]]) -> RenderIntent:
    et = _expl_type(expl)
    if et in (
        "warning",
        "progress",
        "waiting",
        "requirement",
        "review",
        "neutral",
        "completion",
    ):
        return cast(RenderIntent, et)
    return "neutral"


def _render_intent_for_best_action(key: str, expl: Optional[Dict[str, Any]]) -> RenderIntent:
    et = _expl_type(expl)
    if key in REQUIREMENT_ACTION_KEYS or et == "requirement":
        return "requirement"
    if key in REVIEW_INLINE_ACTION_KEYS or et == "review":
        return "review"
    if et == "warning":
        return "warning"
    if et == "waiting":
        return "waiting"
    return "progress"


def _append_support(
    out: List[SupportingSurface],
    surf: SupportingSurface,
    max_n: int = 2,
) -> None:
    if len(out) >= max_n:
        return
    out.append(surf)


def _supporting_from_secondary(
    item: Dict[str, Any],
    *,
    guidance: Optional[Dict[str, Any]],
    best_action: Optional[Dict[str, Any]],
    best_action_explanation: Optional[Dict[str, Any]],
    primary_kind: str,
    primary_surface_type: PrimarySurfaceType,
) -> Optional[SupportingSurface]:
    kind = str(item.get("kind") or "")
    if kind == "explanation" and best_action_explanation:
        ri = _render_intent_from_explanation(best_action_explanation)
        if ri == "completion":
            ri = "neutral"
        return SupportingSurface(
            surface_type="support_strip",
            attention_level="supportive",
            render_intent=ri,
            content_source="best_action_explanation",
            action_presentation="informational_only",
            reason_code="explanation_maps_to_support_surface",
        )
    if kind == "best_action" and best_action:
        ri = _render_intent_for_best_action(_best_key(best_action), best_action_explanation)
        st: SupportingSurfaceType = "inline_card"
        if primary_surface_type == "warning_banner":
            st = "inline_card"
        elif primary_kind == "explanation":
            st = "support_strip"
        ap: ActionPresentation = (
            "secondary_cta"
            if primary_surface_type == "warning_banner"
            else "informational_only"
        )
        return SupportingSurface(
            surface_type=st,
            attention_level="supportive",
            render_intent=ri,
            content_source="best_action",
            action_presentation=ap,
            reason_code="best_action_maps_to_support_surface",
        )
    if kind == "guidance" and guidance:
        gt = _guidance_type(guidance)
        ri: RenderIntent = "warning" if gt == "warning" else "neutral"
        return SupportingSurface(
            surface_type="passive_status",
            attention_level="quiet",
            render_intent=ri,
            content_source="guidance",
            action_presentation="informational_only",
            reason_code="guidance_maps_to_supporting_surface",
        )
    if kind == "candidate_list":
        return SupportingSurface(
            surface_type="candidate_list",
            attention_level="quiet",
            render_intent="review",
            content_source="candidate_list",
            action_presentation="secondary_cta",
            reason_code="candidate_list_maps_to_supporting_surface",
        )
    return None


def compute_ux_surface_contract(
    *,
    guidance: Optional[Dict[str, Any]],
    best_action: Optional[Dict[str, Any]],
    best_action_explanation: Optional[Dict[str, Any]],
    delivery_prioritization: Optional[Dict[str, Any]],
    readiness_context: Optional[Dict[str, Any]] = None,
) -> UxSurfaceContract:
    pf, secondary_items = _parse_dp(delivery_prioritization)
    pf_kind = str(pf.get("kind") or "")
    pf_reason = str(pf.get("reasonCode") or "")
    completed = _overall(readiness_context) == "completed" or pf_reason == (
        "completed_state_no_primary_action"
    )

    supporting: List[SupportingSurface] = []

    # --- F: completed ---
    if completed:
        primary = PrimarySurface(
            surface_type="completion_status",
            attention_level="quiet",
            render_intent="completion",
            content_source="status",
            action_presentation="none",
            reason_code="completed_posture_maps_to_completion_status",
        )
        return UxSurfaceContract(primary_surface=primary, supporting_surfaces=[])

    # --- A: warning guidance primary ---
    if pf_kind == "guidance" and guidance and _guidance_type(guidance) == "warning":
        has_ba = bool(best_action)
        primary = PrimarySurface(
            surface_type="warning_banner",
            attention_level="dominant",
            render_intent="warning",
            content_source="guidance",
            action_presentation="secondary_cta" if has_ba else "informational_only",
            reason_code="warning_guidance_maps_to_banner",
        )
        for item in secondary_items:
            s = _supporting_from_secondary(
                item,
                guidance=guidance,
                best_action=best_action,
                best_action_explanation=best_action_explanation,
                primary_kind=pf_kind,
                primary_surface_type="warning_banner",
            )
            if s:
                _append_support(supporting, s)
        return UxSurfaceContract(primary_surface=primary, supporting_surfaces=supporting)

    # --- C: waiting (explanation or status primary) ---
    if pf_kind == "explanation" or (
        pf_kind == "status" and pf_reason == "waiting_state_status_primary"
    ):
        expl_waiting = _expl_type(best_action_explanation) == "waiting"
        src: PrimaryContentSource = (
            "best_action_explanation"
            if best_action_explanation and (pf_kind == "explanation" or expl_waiting)
            else "status"
        )
        primary = PrimarySurface(
            surface_type="passive_status",
            attention_level="strong" if pf_kind == "explanation" else "supportive",
            render_intent="waiting",
            content_source=src,
            action_presentation="informational_only",
            reason_code="waiting_posture_maps_to_passive_status",
        )
        for item in secondary_items:
            s = _supporting_from_secondary(
                item,
                guidance=guidance,
                best_action=best_action,
                best_action_explanation=best_action_explanation,
                primary_kind=pf_kind,
                primary_surface_type="passive_status",
            )
            if s:
                _append_support(supporting, s)
        return UxSurfaceContract(primary_surface=primary, supporting_surfaces=supporting)

    # --- B, D, E: best action primary ---
    if pf_kind == "best_action" and best_action:
        key = _best_key(best_action)
        et = _expl_type(best_action_explanation)
        avail = str(best_action.get("availability") or "ready")

        if key in REVIEW_INLINE_ACTION_KEYS:
            primary = PrimarySurface(
                surface_type="inline_card",
                attention_level="dominant",
                render_intent="review",
                content_source="best_action",
                action_presentation="primary_cta",
                reason_code="review_action_maps_to_inline_card",
            )
        elif key in REQUIREMENT_ACTION_KEYS:
            st: PrimarySurfaceType = "hero_panel"
            att: PrimaryAttention = "dominant"
            if key == "upload_proof_documents":
                st = "hero_panel"
                att = "strong"
            primary = PrimarySurface(
                surface_type=st,
                attention_level=att,
                render_intent="requirement",
                content_source="best_action",
                action_presentation="primary_cta",
                reason_code="requirement_action_maps_to_primary_surface",
            )
        elif key in HERO_PROGRESS_ACTION_KEYS:
            primary = PrimarySurface(
                surface_type="hero_panel",
                attention_level="strong",
                render_intent="progress",
                content_source="best_action",
                action_presentation="primary_cta",
                reason_code="best_action_progress_maps_to_hero_panel",
            )
        elif key == "wait_for_processing":
            primary = PrimarySurface(
                surface_type="passive_status",
                attention_level="supportive",
                render_intent="waiting",
                content_source="best_action",
                action_presentation="informational_only",
                reason_code="waiting_posture_maps_to_passive_status",
            )
        elif avail == "blocked":
            primary = PrimarySurface(
                surface_type="inline_card",
                attention_level="strong",
                render_intent=_render_intent_for_best_action(key, best_action_explanation),
                content_source="best_action",
                action_presentation="primary_cta",
                reason_code="requirement_action_maps_to_primary_surface",
            )
        else:
            primary = PrimarySurface(
                surface_type="hero_panel",
                attention_level="dominant",
                render_intent=_render_intent_for_best_action(key, best_action_explanation),
                content_source="best_action",
                action_presentation="primary_cta",
                reason_code="best_action_progress_maps_to_hero_panel",
            )

        for item in secondary_items:
            s = _supporting_from_secondary(
                item,
                guidance=guidance,
                best_action=best_action,
                best_action_explanation=best_action_explanation,
                primary_kind=pf_kind,
                primary_surface_type=primary.surface_type,
            )
            if s:
                _append_support(supporting, s)
        return UxSurfaceContract(primary_surface=primary, supporting_surfaces=supporting)

    # Guidance primary (non-warning): treat as passive / informational
    if pf_kind == "guidance" and guidance:
        primary = PrimarySurface(
            surface_type="inline_card",
            attention_level="strong",
            render_intent="neutral",
            content_source="guidance",
            action_presentation="informational_only",
            reason_code="guidance_maps_to_supporting_surface",
        )
        for item in secondary_items:
            s = _supporting_from_secondary(
                item,
                guidance=guidance,
                best_action=best_action,
                best_action_explanation=best_action_explanation,
                primary_kind=pf_kind,
                primary_surface_type="inline_card",
            )
            if s:
                _append_support(supporting, s)
        return UxSurfaceContract(primary_surface=primary, supporting_surfaces=supporting)

    # Status / neutral fallback
    primary = PrimarySurface(
        surface_type="passive_status",
        attention_level="quiet",
        render_intent="neutral",
        content_source="status",
        action_presentation="none",
        reason_code="neutral_status_maps_to_passive_surface",
    )
    return UxSurfaceContract(primary_surface=primary, supporting_surfaces=[])


def compute_ux_surface_contract_user_api(
    *,
    guidance: Optional[Dict[str, Any]],
    best_action: Optional[Dict[str, Any]],
    best_action_explanation: Optional[Dict[str, Any]],
    delivery_prioritization: Optional[Dict[str, Any]],
    readiness_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return compute_ux_surface_contract(
        guidance=guidance,
        best_action=best_action,
        best_action_explanation=best_action_explanation,
        delivery_prioritization=delivery_prioritization,
        readiness_context=readiness_context,
    ).to_user_api_dict()


def audit_ux_surface_contract_for_bundle_inputs(
    *,
    guidance: Optional[Dict[str, Any]],
    best_action: Optional[Dict[str, Any]],
    best_action_explanation: Optional[Dict[str, Any]],
    delivery_prioritization: Optional[Dict[str, Any]],
    readiness_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    c = compute_ux_surface_contract(
        guidance=guidance,
        best_action=best_action,
        best_action_explanation=best_action_explanation,
        delivery_prioritization=delivery_prioritization,
        readiness_context=readiness_context,
    )
    return {
        "uxSurfaceContract": c.to_audit_dict(),
        "surfaceContractVersion": c.surface_contract_version,
        "primarySurfaceReasonCode": c.primary_surface.reason_code,
        "supportingSurfaceTypes": [s.surface_type for s in c.supporting_surfaces],
    }
