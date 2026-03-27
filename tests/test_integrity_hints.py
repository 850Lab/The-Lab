"""Unit tests for workflow integrity hints (deterministic flags + nextRequiredAction)."""

from unittest.mock import patch

from services.workflow.integrity_hints_service import (
    build_integrity_hints,
    next_required_action_from_head,
)


def test_next_required_action_pre_pay_collapses_to_upload():
    assert next_required_action_from_head("upload", "active") == "upload"
    assert next_required_action_from_head("parse_analyze", "active") == "upload"
    assert next_required_action_from_head("review_claims", "active") == "upload"
    assert next_required_action_from_head("select_disputes", "active") == "upload"


def test_next_required_action_done_is_track():
    assert next_required_action_from_head(None, "done") == "track"


@patch(
    "services.workflow.integrity_hints_service._mailing_debit_without_mailed_send",
    return_value=False,
)
@patch("services.workflow.integrity_hints_service.lob_client.customer_mail_send_blocked_reason")
@patch("services.workflow.integrity_hints_service.auth.has_entitlement", return_value=True)
@patch("services.workflow.integrity_hints_service.db.has_proof_docs")
@patch("services.workflow.integrity_hints_service.needed_letters_from_workflow_session", return_value=1)
@patch("services.workflow.integrity_hints_service.fetch_session")
@patch("services.workflow.integrity_hints_service.fetch_steps")
def test_entitlements_but_payment_incomplete(
    mock_steps,
    mock_session,
    _needed,
    mock_proof,
    _has_ent,
    _lob_block,
    _mail_debit,
):
    mock_session.return_value = {
        "user_id": 1,
        "overall_status": "active",
        "current_step": "payment",
        "metadata": {},
    }
    mock_steps.return_value = [
        {"step_id": "upload", "status": "completed"},
        {"step_id": "parse_analyze", "status": "completed"},
        {"step_id": "review_claims", "status": "completed"},
        {"step_id": "select_disputes", "status": "completed"},
        {"step_id": "payment", "status": "available"},
    ]
    mock_proof.return_value = {"both": True}
    _lob_block.return_value = None

    h = build_integrity_hints(1, "wf-1")
    assert h["entitlementsButPaymentIncomplete"] is True
    assert h["nextRequiredAction"] == "pay"


@patch(
    "services.workflow.integrity_hints_service._mailing_debit_without_mailed_send",
    return_value=False,
)
@patch("services.workflow.integrity_hints_service.lob_client.customer_mail_send_blocked_reason")
@patch("services.workflow.integrity_hints_service.auth.has_entitlement", return_value=True)
@patch("services.workflow.integrity_hints_service.db.has_proof_docs")
@patch("services.workflow.integrity_hints_service.needed_letters_from_workflow_session", return_value=1)
@patch("services.workflow.integrity_hints_service.fetch_session")
@patch("services.workflow.integrity_hints_service.fetch_steps")
def test_proof_incomplete_on_mail_forces_next_proof(
    mock_steps,
    mock_session,
    _needed,
    mock_proof,
    _has_ent,
    _lob_block,
    _mail_debit,
):
    mock_session.return_value = {
        "user_id": 1,
        "overall_status": "active",
        "current_step": "mail",
        "metadata": {},
    }
    mock_steps.return_value = [
        {"step_id": s, "status": "completed"}
        for s in (
            "upload",
            "parse_analyze",
            "review_claims",
            "select_disputes",
            "payment",
            "letter_generation",
            "proof_attachment",
        )
    ] + [{"step_id": "mail", "status": "available"}]
    mock_proof.return_value = {"both": False}
    _lob_block.return_value = None

    h = build_integrity_hints(1, "wf-1")
    assert h["proofIncomplete"] is True
    assert h["nextRequiredAction"] == "proof"


@patch(
    "services.workflow.integrity_hints_service._mailing_debit_without_mailed_send",
    return_value=False,
)
@patch("services.workflow.integrity_hints_service.lob_client.customer_mail_send_blocked_reason")
@patch("services.workflow.integrity_hints_service.auth.has_entitlement", return_value=True)
@patch("services.workflow.integrity_hints_service.db.has_proof_docs")
@patch("services.workflow.integrity_hints_service.needed_letters_from_workflow_session", return_value=1)
@patch("services.workflow.integrity_hints_service.fetch_session")
@patch("services.workflow.integrity_hints_service.fetch_steps")
def test_workflow_step_mismatch_session_current_step_wrong(
    mock_steps,
    mock_session,
    _needed,
    mock_proof,
    _has_ent,
    _lob_block,
    _mail_debit,
):
    mock_session.return_value = {
        "user_id": 1,
        "overall_status": "active",
        "current_step": "upload",
        "metadata": {},
    }
    mock_steps.return_value = [
        {"step_id": "upload", "status": "completed"},
        {"step_id": "parse_analyze", "status": "available"},
    ]
    mock_proof.return_value = {"both": True}
    _lob_block.return_value = None

    h = build_integrity_hints(1, "wf-1")
    assert h["workflowStepMismatch"] is True
