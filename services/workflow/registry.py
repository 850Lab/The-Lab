"""
Linear workflow definition: step registry (single source for progression rules).

TODO(next phase): Load from DB or versioned JSON when multiple workflow families exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Final, List, Tuple


@dataclass(frozen=True)
class StepDefinition:
    """One node in the linear dispute workflow."""

    step_id: str
    name: str
    required_inputs: Tuple[str, ...] = ()
    completion_conditions: Tuple[str, ...] = ()
    failure_conditions: Tuple[str, ...] = ()
    next_steps: Tuple[str, ...] = ()

    def to_public_dict(self) -> dict:
        return {
            "stepId": self.step_id,
            "name": self.name,
            "requiredInputs": list(self.required_inputs),
            "completionConditions": list(self.completion_conditions),
            "failureConditions": list(self.failure_conditions),
            "nextSteps": list(self.next_steps),
        }


def _step(
    step_id: str,
    name: str,
    *,
    required_inputs: Tuple[str, ...] = (),
    completion_conditions: Tuple[str, ...] = (),
    failure_conditions: Tuple[str, ...] = (),
    next_step: str | None = None,
) -> StepDefinition:
    nxt: Tuple[str, ...] = (next_step,) if next_step else ()
    return StepDefinition(
        step_id=step_id,
        name=name,
        required_inputs=required_inputs,
        completion_conditions=completion_conditions,
        failure_conditions=failure_conditions,
        next_steps=nxt,
    )


# Linear chain: upload → … → track
STEP_DEFINITIONS: Final[List[StepDefinition]] = [
    _step(
        "upload",
        "Upload credit report",
        required_inputs=("credit_report_file",),
        completion_conditions=("file_stored", "bureau_detected_or_selected"),
        failure_conditions=("upload_rejected", "virus_scan_failed"),
        next_step="parse_analyze",
    ),
    _step(
        "parse_analyze",
        "Parse & analyze",
        required_inputs=("report_id",),
        completion_conditions=("parse_succeeded", "analysis_record_created"),
        failure_conditions=("parse_failed", "unsupported_format"),
        next_step="review_claims",
    ),
    _step(
        "review_claims",
        "Review claims",
        required_inputs=("analysis_summary",),
        completion_conditions=("consumer_reviewed_items",),
        failure_conditions=("session_abandoned",),
        next_step="select_disputes",
    ),
    _step(
        "select_disputes",
        "Select disputes",
        required_inputs=("selected_item_ids",),
        completion_conditions=("selection_confirmed",),
        failure_conditions=("no_items_selected",),
        next_step="payment",
    ),
    _step(
        "payment",
        "Payment",
        required_inputs=("payment_intent_or_session",),
        completion_conditions=("payment_captured_or_waived",),
        failure_conditions=("payment_failed", "payment_canceled"),
        next_step="letter_generation",
    ),
    _step(
        "letter_generation",
        "Letter generation",
        required_inputs=("strategy_snapshot",),
        completion_conditions=("letters_generated",),
        failure_conditions=("generation_failed",),
        next_step="proof_attachment",
    ),
    _step(
        "proof_attachment",
        "Proof & signature",
        required_inputs=("id_document", "proof_of_address", "signature"),
        completion_conditions=("proof_bundle_complete",),
        failure_conditions=("validation_failed",),
        next_step="mail",
    ),
    _step(
        "mail",
        "Mail disputes",
        required_inputs=("mail_batch_id",),
        completion_conditions=("mail_submitted",),
        failure_conditions=("carrier_rejected", "address_invalid"),
        next_step="track",
    ),
    _step(
        "track",
        "Track responses",
        required_inputs=("tracking_handles",),
        completion_conditions=("monitoring_active",),
        failure_conditions=("tracking_unavailable",),
        next_step=None,
    ),
]

STEP_REGISTRY: Final[Dict[str, StepDefinition]] = {
    s.step_id: s for s in STEP_DEFINITIONS
}
LINEAR_STEP_ORDER: Final[Tuple[str, ...]] = tuple(s.step_id for s in STEP_DEFINITIONS)

WORKFLOW_TYPE_DEFAULT: Final[str] = "dispute_linear_v1"
DEFINITION_VERSION: Final[int] = 1
ENGINE_VERSION: Final[int] = 1

# Steps that use async_task_state when started via API (queued → worker running → complete).
ASYNC_MANAGED_STEPS: Final[Tuple[str, ...]] = (
    "parse_analyze",
    "letter_generation",
    "mail",
)


def get_step_definition(step_id: str) -> StepDefinition | None:
    return STEP_REGISTRY.get(step_id)


def index_of(step_id: str) -> int:
    try:
        return LINEAR_STEP_ORDER.index(step_id)
    except ValueError:
        return -1
