"""
O.R.I.O.N. V1.4 — deterministic delivery prioritization (not orchestration, no AI).

Interprets existing ORION bundle fragments only; does not query event history.

ORION is deterministic. Do NOT inject AI logic here. AI layers must consume ORION outputs, not modify them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

DELIVERY_PRIORITIZATION_VERSION = "orion_delivery_prioritization_v1"

PrimaryKind = Literal["guidance", "best_action", "explanation", "status"]
PrimaryEmphasis = Literal["high", "medium"]
SecondaryKind = Literal[
    "guidance", "best_action", "explanation", "candidate_list", "status"
]
SecondaryEmphasis = Literal["medium", "low"]
SuppressedKind = Literal[
    "guidance", "best_action", "explanation", "candidate_list", "status"
]


@dataclass
class PrimaryFocus:
    kind: PrimaryKind
    emphasis: PrimaryEmphasis
    reason_code: str

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "emphasis": self.emphasis,
            "reasonCode": self.reason_code,
        }


@dataclass
class SecondarySupportItem:
    kind: SecondaryKind
    emphasis: SecondaryEmphasis
    reason_code: str

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "emphasis": self.emphasis,
            "reasonCode": self.reason_code,
        }


@dataclass
class SuppressedSignal:
    kind: SuppressedKind
    reason_code: str

    def to_api_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "reasonCode": self.reason_code}


@dataclass
class DeliveryPrioritization:
    primary_focus: PrimaryFocus
    secondary_support: List[SecondarySupportItem] = field(default_factory=list)
    suppressed_signals: List[SuppressedSignal] = field(default_factory=list)
    prioritization_version: str = DELIVERY_PRIORITIZATION_VERSION

    def to_user_api_dict(self) -> Dict[str, Any]:
        return {
            "primaryFocus": self.primary_focus.to_api_dict(),
            "secondarySupport": [s.to_api_dict() for s in self.secondary_support],
            "suppressedSignals": [s.to_api_dict() for s in self.suppressed_signals],
            "prioritizationVersion": self.prioritization_version,
        }

    def to_audit_dict(self) -> Dict[str, Any]:
        return self.to_user_api_dict()


def _truthy_display_eligible(g: Dict[str, Any]) -> bool:
    if g.get("displayEligible") is False:
        return False
    return True


def _guidance_type(g: Optional[Dict[str, Any]]) -> str:
    if not g or not isinstance(g, dict):
        return ""
    return str(g.get("type") or "").strip()


def _guidance_target_step(g: Dict[str, Any]) -> Optional[str]:
    ra = g.get("recommendedAction")
    if not isinstance(ra, dict):
        return None
    ts = ra.get("targetStepId")
    if ts is None:
        return None
    s = str(ts).strip()
    return s or None


def _best_target(ba: Dict[str, Any]) -> Optional[str]:
    ts = ba.get("targetStepId")
    if ts is None:
        return None
    s = str(ts).strip()
    return s or None


def _best_key(ba: Optional[Dict[str, Any]]) -> str:
    if not ba or not isinstance(ba, dict):
        return ""
    return str(ba.get("actionKey") or "").strip()


def _explanation_type(expl: Optional[Dict[str, Any]]) -> str:
    if not expl or not isinstance(expl, dict):
        return ""
    return str(expl.get("explanationType") or "").strip()


def _overall_status(ctx: Optional[Dict[str, Any]]) -> str:
    if not ctx or not isinstance(ctx, dict):
        return ""
    return str(ctx.get("overallStatus") or "").strip()


def _phase(ctx: Optional[Dict[str, Any]]) -> str:
    if not ctx or not isinstance(ctx, dict):
        return ""
    return str(ctx.get("phase") or "").strip()


REVIEW_ORIENTED_ACTION_KEYS = frozenset(
    {
        "review_claims",
        "review_dispute_selection",
        "review_generated_letters",
        "review_escalation_options",
        "check_tracking_status",
    }
)


def _is_review_oriented_best(ba: Optional[Dict[str, Any]]) -> bool:
    if not ba:
        return False
    if _best_key(ba) in REVIEW_ORIENTED_ACTION_KEYS:
        return True
    return str(ba.get("actionType") or "").strip() == "review"


def _instruction_aligns_guidance_to_best(
    guidance: Optional[Dict[str, Any]], best_action: Optional[Dict[str, Any]]
) -> bool:
    if not guidance or not best_action:
        return False
    if _guidance_type(guidance) != "instruction":
        return False
    gt = _guidance_target_step(guidance)
    bt = _best_target(best_action)
    if not gt or not bt:
        return False
    return gt == bt


def _suppress_candidate_list(
    *,
    completed: bool,
    warning_primary: bool,
    waiting_posture: bool,
    instruction_aligned: bool,
    len_candidates: int,
) -> bool:
    if completed or warning_primary or waiting_posture or instruction_aligned:
        return True
    if len_candidates <= 1:
        return True
    return False


def _should_offer_candidate_secondary(
    *,
    suppress_candidates: bool,
    len_candidates: int,
    primary_kind: str,
) -> bool:
    if suppress_candidates or len_candidates < 2:
        return False
    return primary_kind == "best_action"


def _append_secondary(
    out: List[SecondarySupportItem],
    kind: SecondaryKind,
    emphasis: SecondaryEmphasis,
    code: str,
) -> None:
    if len(out) >= 2:
        return
    out.append(SecondarySupportItem(kind=kind, emphasis=emphasis, reason_code=code))


def compute_delivery_prioritization(
    *,
    guidance: Optional[Dict[str, Any]],
    best_action: Optional[Dict[str, Any]],
    action_candidates: Optional[List[Dict[str, Any]]],
    best_action_explanation: Optional[Dict[str, Any]],
    readiness_context: Optional[Dict[str, Any]] = None,
) -> DeliveryPrioritization:
    """
    Deterministic prioritization from ORION bundle inputs only.
    """
    candidates = list(action_candidates) if action_candidates else []
    len_c = len(candidates)

    overall = _overall_status(readiness_context)
    phase = _phase(readiness_context)
    completed = overall == "completed" or (
        phase == "done" and not best_action and not guidance
    )

    expl_type = _explanation_type(best_action_explanation)
    bkey = _best_key(best_action)
    waiting_posture = bkey == "wait_for_processing" or expl_type == "waiting"

    gtype = _guidance_type(guidance)
    warning_eligible = (
        guidance is not None
        and gtype == "warning"
        and _truthy_display_eligible(guidance)
    )
    instruction_aligned = _instruction_aligns_guidance_to_best(guidance, best_action)

    suppress_c = _suppress_candidate_list(
        completed=completed,
        warning_primary=warning_eligible,
        waiting_posture=waiting_posture,
        instruction_aligned=instruction_aligned,
        len_candidates=len_c,
    )

    secondary: List[SecondarySupportItem] = []
    suppressed: List[SuppressedSignal] = []

    def add_suppressed(kind: SuppressedKind, code: str) -> None:
        suppressed.append(SuppressedSignal(kind=kind, reason_code=code))

    # --- F: completed / neutral ---
    if completed:
        pf = PrimaryFocus(
            kind="status",
            emphasis="high",
            reason_code="completed_state_no_primary_action",
        )
        if guidance:
            add_suppressed("guidance", "guidance_suppressed_completed_state")
        if best_action:
            add_suppressed("best_action", "best_action_suppressed_completed_state")
        if best_action_explanation:
            add_suppressed("explanation", "explanation_suppressed_completed_state")
        if len_c:
            add_suppressed("candidate_list", "candidate_list_suppressed_completed_state")
        return DeliveryPrioritization(
            primary_focus=pf,
            secondary_support=secondary,
            suppressed_signals=suppressed,
        )

    # --- A: warning guidance dominates ---
    if warning_eligible:
        pf = PrimaryFocus(
            kind="guidance",
            emphasis="high",
            reason_code="warning_guidance_dominates",
        )
        if best_action:
            _append_secondary(
                secondary,
                "best_action",
                "medium",
                "best_action_secondary_under_warning",
            )
        if best_action_explanation:
            _append_secondary(
                secondary,
                "explanation",
                "medium",
                "explanation_secondary_for_confidence",
            )
        if len_c:
            add_suppressed("candidate_list", "candidate_list_suppressed_to_reduce_noise")
        return DeliveryPrioritization(
            primary_focus=pf,
            secondary_support=secondary,
            suppressed_signals=suppressed,
        )

    # --- D: waiting ---
    if waiting_posture:
        if best_action_explanation:
            pf = PrimaryFocus(
                kind="explanation",
                emphasis="high",
                reason_code="waiting_state_explanation_primary",
            )
        else:
            pf = PrimaryFocus(
                kind="status",
                emphasis="high",
                reason_code="waiting_state_status_primary",
            )
        if best_action:
            _append_secondary(
                secondary,
                "best_action",
                "medium",
                "best_action_secondary_wait_anchor",
            )
        if len_c:
            add_suppressed("candidate_list", "candidate_list_suppressed_to_reduce_noise")
        if guidance and gtype in ("nudge", "optimization"):
            add_suppressed("guidance", "low_value_guidance_suppressed_waiting")
        elif guidance and gtype not in ("instruction",):
            add_suppressed("guidance", "guidance_suppressed_waiting_focus")
        return DeliveryPrioritization(
            primary_focus=pf,
            secondary_support=secondary,
            suppressed_signals=suppressed,
        )

    # --- B: instruction aligns with best action ---
    if instruction_aligned and best_action:
        pf = PrimaryFocus(
            kind="best_action",
            emphasis="high",
            reason_code="instruction_supports_best_action",
        )
        _append_secondary(
            secondary,
            "guidance",
            "medium",
            "guidance_secondary_reinforces_action",
        )
        if best_action_explanation:
            _append_secondary(
                secondary,
                "explanation",
                "medium",
                "explanation_secondary_for_confidence",
            )
        if len_c:
            add_suppressed("candidate_list", "candidate_list_suppressed_to_reduce_noise")
        return DeliveryPrioritization(
            primary_focus=pf,
            secondary_support=secondary,
            suppressed_signals=suppressed,
        )

    # --- E: review-oriented best action ---
    if best_action and _is_review_oriented_best(best_action):
        pf = PrimaryFocus(
            kind="best_action",
            emphasis="high",
            reason_code="review_action_primary",
        )
        if best_action_explanation:
            _append_secondary(
                secondary,
                "explanation",
                "medium",
                "explanation_secondary_for_confidence",
            )
        if (
            not suppress_c
            and _should_offer_candidate_secondary(
                suppress_candidates=False,
                len_candidates=len_c,
                primary_kind="best_action",
            )
        ):
            _append_secondary(
                secondary,
                "candidate_list",
                "low",
                "candidate_list_secondary_multiple_paths",
            )
        if guidance and gtype != "warning":
            _append_secondary(
                secondary,
                "guidance",
                "low",
                "guidance_secondary_non_blocking",
            )
        if suppress_c and len_c:
            add_suppressed("candidate_list", "candidate_list_suppressed_to_reduce_noise")
        return DeliveryPrioritization(
            primary_focus=pf,
            secondary_support=secondary,
            suppressed_signals=suppressed,
        )

    # --- C: default — best action primary if present ---
    if best_action:
        pf = PrimaryFocus(
            kind="best_action",
            emphasis="high",
            reason_code="best_action_primary_no_guidance"
            if not guidance
            else "best_action_primary_over_secondary_guidance",
        )
        if best_action_explanation:
            _append_secondary(
                secondary,
                "explanation",
                "medium",
                "explanation_secondary_for_confidence",
            )
        if (
            not suppress_c
            and _should_offer_candidate_secondary(
                suppress_candidates=False,
                len_candidates=len_c,
                primary_kind="best_action",
            )
        ):
            _append_secondary(
                secondary,
                "candidate_list",
                "low",
                "candidate_list_secondary_multiple_paths",
            )
        if guidance:
            em: SecondaryEmphasis = "low" if gtype in ("nudge", "optimization") else "medium"
            code = (
                "guidance_secondary_low_priority"
                if em == "low"
                else "guidance_secondary_contextual"
            )
            _append_secondary(secondary, "guidance", em, code)
        if suppress_c and len_c:
            add_suppressed("candidate_list", "candidate_list_suppressed_to_reduce_noise")
        return DeliveryPrioritization(
            primary_focus=pf,
            secondary_support=secondary,
            suppressed_signals=suppressed,
        )

    # Guidance but no best action
    if guidance:
        pf = PrimaryFocus(
            kind="guidance",
            emphasis="high",
            reason_code="guidance_primary_no_best_action",
        )
        if best_action_explanation:
            _append_secondary(
                secondary,
                "explanation",
                "medium",
                "explanation_secondary_for_confidence",
            )
        if len_c:
            add_suppressed("candidate_list", "candidate_list_suppressed_to_reduce_noise")
        return DeliveryPrioritization(
            primary_focus=pf,
            secondary_support=secondary,
            suppressed_signals=suppressed,
        )

    # Fallback: status
    pf = PrimaryFocus(
        kind="status",
        emphasis="medium",
        reason_code="neutral_status_no_action_signals",
    )
    if len_c:
        add_suppressed("candidate_list", "candidate_list_suppressed_to_reduce_noise")
    return DeliveryPrioritization(
        primary_focus=pf,
        secondary_support=secondary,
        suppressed_signals=suppressed,
    )


def compute_delivery_prioritization_user_api(
    *,
    guidance: Optional[Dict[str, Any]],
    best_action: Optional[Dict[str, Any]],
    action_candidates: Optional[List[Dict[str, Any]]],
    best_action_explanation: Optional[Dict[str, Any]],
    readiness_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return compute_delivery_prioritization(
        guidance=guidance,
        best_action=best_action,
        action_candidates=action_candidates,
        best_action_explanation=best_action_explanation,
        readiness_context=readiness_context,
    ).to_user_api_dict()


def audit_delivery_prioritization_for_bundle_inputs(
    *,
    guidance: Optional[Dict[str, Any]],
    best_action: Optional[Dict[str, Any]],
    action_candidates: Optional[List[Dict[str, Any]]],
    best_action_explanation: Optional[Dict[str, Any]],
    readiness_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Operator inspection: same shape as customer API plus stable audit parity."""
    dp = compute_delivery_prioritization(
        guidance=guidance,
        best_action=best_action,
        action_candidates=action_candidates,
        best_action_explanation=best_action_explanation,
        readiness_context=readiness_context,
    )
    return {
        "deliveryPrioritization": dp.to_audit_dict(),
        "prioritizationVersion": dp.prioritization_version,
        "primaryReasonCode": dp.primary_focus.reason_code,
        "secondaryKinds": [s.kind for s in dp.secondary_support],
        "suppressedKinds": [s.kind for s in dp.suppressed_signals],
    }
