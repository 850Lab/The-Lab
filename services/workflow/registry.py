"""
Linear workflow definitions: one registry per ``workflow_type`` (dispute consumer vs org program).

All step_ids are globally unique so ``STEP_REGISTRY`` and engine transitions stay unambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Final, List, Tuple


@dataclass(frozen=True)
class StepDefinition:
    """One node in a linear workflow."""

    step_id: str
    name: str
    required_inputs: Tuple[str, ...] = ()
    completion_conditions: Tuple[str, ...] = ()
    failure_conditions: Tuple[str, ...] = ()
    next_steps: Tuple[str, ...] = ()
    allowed_entry_statuses: Tuple[str, ...] = ()

    def to_public_dict(self) -> dict:
        return {
            "stepId": self.step_id,
            "name": self.name,
            "requiredInputs": list(self.required_inputs),
            "completionConditions": list(self.completion_conditions),
            "failureConditions": list(self.failure_conditions),
            "nextSteps": list(self.next_steps),
            "allowedEntryStatuses": list(self.allowed_entry_statuses),
        }


def _step(
    step_id: str,
    name: str,
    *,
    required_inputs: Tuple[str, ...] = (),
    completion_conditions: Tuple[str, ...] = (),
    failure_conditions: Tuple[str, ...] = (),
    next_step: str | None = None,
    allowed_entry_statuses: Tuple[str, ...],
) -> StepDefinition:
    nxt: Tuple[str, ...] = (next_step,) if next_step else ()
    return StepDefinition(
        step_id=step_id,
        name=name,
        required_inputs=required_inputs,
        completion_conditions=completion_conditions,
        failure_conditions=failure_conditions,
        next_steps=nxt,
        allowed_entry_statuses=allowed_entry_statuses,
    )


# --- Consumer dispute chain (original) ------------------------------------
DISPUTE_STEP_DEFINITIONS: Final[List[StepDefinition]] = [
    _step(
        "upload",
        "Upload credit report",
        required_inputs=("credit_report_file",),
        completion_conditions=("file_stored", "bureau_detected_or_selected"),
        failure_conditions=("upload_rejected", "virus_scan_failed"),
        next_step="parse_analyze",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "parse_analyze",
        "Parse & analyze",
        required_inputs=("report_id",),
        completion_conditions=("parse_succeeded", "analysis_record_created"),
        failure_conditions=("parse_failed", "unsupported_format"),
        next_step="review_claims",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "review_claims",
        "Review claims",
        required_inputs=("analysis_summary",),
        completion_conditions=("consumer_reviewed_items",),
        failure_conditions=("session_abandoned",),
        next_step="select_disputes",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "select_disputes",
        "Select disputes",
        required_inputs=("selected_item_ids",),
        completion_conditions=("selection_confirmed",),
        failure_conditions=("no_items_selected",),
        next_step="payment",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "payment",
        "Payment",
        required_inputs=("payment_intent_or_session",),
        completion_conditions=("payment_captured_or_waived",),
        failure_conditions=("payment_failed", "payment_canceled"),
        next_step="letter_generation",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "letter_generation",
        "Letter generation",
        required_inputs=("strategy_snapshot",),
        completion_conditions=("letters_generated",),
        failure_conditions=("generation_failed",),
        next_step="proof_attachment",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "proof_attachment",
        "Proof & signature",
        required_inputs=("id_document", "proof_of_address", "signature"),
        completion_conditions=("proof_bundle_complete",),
        failure_conditions=("validation_failed",),
        next_step="mail",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "mail",
        "Mail disputes",
        required_inputs=("mail_batch_id",),
        completion_conditions=("mail_submitted",),
        failure_conditions=("carrier_rejected", "address_invalid"),
        next_step="track",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "track",
        "Track responses",
        required_inputs=("tracking_handles",),
        completion_conditions=("monitoring_active",),
        failure_conditions=("tracking_unavailable",),
        next_step=None,
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
]

# --- Organization hosted program (maps to PROGRAM_STEPS UX / gates) ---------
ORG_PROGRAM_STEP_DEFINITIONS: Final[List[StepDefinition]] = [
    _step(
        "orgprog_enrollment",
        "Program enrollment",
        completion_conditions=("seat_active",),
        next_step="orgprog_upload",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "orgprog_upload",
        "Upload credit report",
        required_inputs=("credit_report_file",),
        completion_conditions=("file_stored",),
        next_step="orgprog_findings_ready",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "orgprog_findings_ready",
        "Findings ready",
        completion_conditions=("analysis_complete",),
        next_step="orgprog_selections_saved",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "orgprog_selections_saved",
        "Selections saved",
        completion_conditions=("selection_confirmed",),
        next_step="orgprog_letters_generated",
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
    _step(
        "orgprog_letters_generated",
        "Letters generated",
        completion_conditions=("letters_generated",),
        next_step=None,
        allowed_entry_statuses=("available", "failed", "in_progress"),
    ),
]

STEP_DEFINITIONS_BY_TYPE: Final[Dict[str, List[StepDefinition]]] = {
    "dispute_linear_v1": list(DISPUTE_STEP_DEFINITIONS),
    "org_program_v1": list(ORG_PROGRAM_STEP_DEFINITIONS),
}

_all_defs: List[StepDefinition] = []
for _lst in STEP_DEFINITIONS_BY_TYPE.values():
    _all_defs.extend(_lst)

STEP_REGISTRY: Final[Dict[str, StepDefinition]] = {s.step_id: s for s in _all_defs}

WORKFLOW_TYPE_DEFAULT: Final[str] = "dispute_linear_v1"
ORG_PROGRAM_WORKFLOW_TYPE: Final[str] = "org_program_v1"

# Back-compat: consumer linear order (many imports use this name).
STEP_DEFINITIONS: Final[List[StepDefinition]] = DISPUTE_STEP_DEFINITIONS
LINEAR_STEP_ORDER: Final[Tuple[str, ...]] = tuple(
    s.step_id for s in DISPUTE_STEP_DEFINITIONS
)

DEFINITION_VERSION: Final[int] = 1
ENGINE_VERSION: Final[int] = 1

# Async-managed steps (consumer mail + parse + letters; org letters completed synchronously in API).
ASYNC_MANAGED_STEPS: Final[Tuple[str, ...]] = (
    "parse_analyze",
    "letter_generation",
    "mail",
)


def linear_order_for(workflow_type: str) -> Tuple[str, ...]:
    wt = (workflow_type or "").strip() or WORKFLOW_TYPE_DEFAULT
    lst = STEP_DEFINITIONS_BY_TYPE.get(wt)
    if not lst:
        lst = STEP_DEFINITIONS_BY_TYPE[WORKFLOW_TYPE_DEFAULT]
    return tuple(s.step_id for s in lst)


def get_step_definition(step_id: str) -> StepDefinition | None:
    return STEP_REGISTRY.get(step_id)


def index_of(step_id: str) -> int:
    try:
        return LINEAR_STEP_ORDER.index(step_id)
    except ValueError:
        return -1
