"""
DB-backed flow gate regression: isolated SQLite workflow + forbidden customer action.

Uses a temp SQLite file and resets the workflow_sqlite module connection so tests do not
depend on the developer's default ``lab_truth/dev_workflow.sqlite``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_forbidden_sequence.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def _step_status(steps: list, step_id: str):
    for r in steps:
        if r.get("step_id") == step_id:
            return r.get("status")
    return None


def test_payment_checkout_blocked_when_workflow_head_is_upload(isolated_workflow_sqlite):
    from services.workflow.engine import WorkflowEngine
    from services.workflow.workflow_flow_gates import (
        ACTION_PAYMENT_CHECKOUT,
        FlowEnforcementError,
        enforce_customer_action,
    )

    eng = WorkflowEngine()
    out = eng.init_workflow(user_id=1, metadata={})
    wid = (out.get("workflowState") or {}).get("workflowId") or ""
    assert wid, "init_workflow should return workflowId in workflowState"

    with pytest.raises(FlowEnforcementError) as excinfo:
        enforce_customer_action(wid, ACTION_PAYMENT_CHECKOUT)
    assert excinfo.value.code == "FLOW_ORDER_VIOLATION"


def test_parse_fail_hook_skipped_when_head_not_upload(isolated_workflow_sqlite):
    """Trusted fail hook must not mark upload failed when linear head is past upload."""
    from services.workflow.engine import WorkflowEngine
    from services.workflow import hooks as workflow_hooks
    from services.workflow.repository import fetch_session

    eng = WorkflowEngine()
    out = eng.init_workflow(user_id=1, metadata={})
    wid = (out.get("workflowState") or {}).get("workflowId") or ""
    assert eng.service_complete_step(
        wid,
        "upload",
        {"test": True},
        audit_source="test",
        audit_user_id=1,
    )
    assert eng.service_complete_step(
        wid,
        "parse_analyze",
        {"test": True},
        audit_source="test",
        audit_user_id=1,
    )
    sess_before = fetch_session(wid)
    assert sess_before
    assert (sess_before.get("overall_status") or "") != "failed"

    workflow_hooks.notify_parse_failed(
        1,
        "should not fail upload — wrong head",
        workflow_id=wid,
    )

    sess_after = fetch_session(wid)
    assert sess_after
    assert (sess_after.get("overall_status") or "") != "failed"


def test_letter_generation_complete_hook_rejected_when_head_is_payment(
    isolated_workflow_sqlite,
):
    """``complete_letter_generation_step`` must not advance when linear head is still payment."""
    from services.workflow.engine import WorkflowEngine
    from services.workflow import hooks as workflow_hooks
    from services.workflow.repository import fetch_steps

    eng = WorkflowEngine()
    out = eng.init_workflow(user_id=1, metadata={})
    wid = (out.get("workflowState") or {}).get("workflowId") or ""

    for sid in ("upload", "parse_analyze", "review_claims", "select_disputes"):
        assert eng.service_complete_step(
            wid,
            sid,
            {"test": True},
            audit_source="test",
            audit_user_id=1,
        ), f"advance to payment head failed at {sid}"

    ok = workflow_hooks.complete_letter_generation_step(
        1, wid, ["experian"], audit_source="test"
    )
    assert ok is False
    steps = fetch_steps(wid)
    assert _step_status(steps, "letter_generation") != "completed"


def test_mail_send_fail_hook_skipped_when_head_is_letter_generation(
    isolated_workflow_sqlite,
):
    """``notify_mail_send_failed`` must not fail the mail step when head is not mail."""
    from services.workflow.engine import WorkflowEngine
    from services.workflow import hooks as workflow_hooks
    from services.workflow.repository import fetch_session, fetch_steps

    eng = WorkflowEngine()
    out = eng.init_workflow(user_id=1, metadata={})
    wid = (out.get("workflowState") or {}).get("workflowId") or ""

    for sid in (
        "upload",
        "parse_analyze",
        "review_claims",
        "select_disputes",
        "payment",
    ):
        assert eng.service_complete_step(
            wid,
            sid,
            {"test": True},
            audit_source="test",
            audit_user_id=1,
        ), f"advance to letter_generation head failed at {sid}"

    sess_before = fetch_session(wid)
    assert sess_before
    assert (sess_before.get("overall_status") or "") != "failed"

    workflow_hooks.notify_mail_send_failed(
        1,
        "LOB_TEST",
        "simulated failure — wrong head",
        workflow_id=wid,
    )

    sess_after = fetch_session(wid)
    assert sess_after
    assert (sess_after.get("overall_status") or "") != "failed"
    steps = fetch_steps(wid)
    assert _step_status(steps, "mail") != "failed"


def test_streamlit_workflow_mutations_disabled_blocks_letter_hook_at_valid_head(
    isolated_workflow_sqlite,
    monkeypatch,
):
    """Env kill-switch: correct head but audit_source streamlit → no mutation."""
    from services.workflow.engine import WorkflowEngine
    from services.workflow import hooks as workflow_hooks
    from services.workflow.repository import fetch_steps

    monkeypatch.setenv("STREAMLIT_WORKFLOW_MUTATIONS_DISABLED", "1")

    eng = WorkflowEngine()
    out = eng.init_workflow(user_id=1, metadata={})
    wid = (out.get("workflowState") or {}).get("workflowId") or ""
    for sid in (
        "upload",
        "parse_analyze",
        "review_claims",
        "select_disputes",
        "payment",
    ):
        assert eng.service_complete_step(
            wid,
            sid,
            {"test": True},
            audit_source="test",
            audit_user_id=1,
        )

    ok_blocked = workflow_hooks.complete_letter_generation_step(
        1, wid, ["experian"], audit_source="streamlit"
    )
    assert ok_blocked is False
    assert _step_status(fetch_steps(wid), "letter_generation") != "completed"

    monkeypatch.delenv("STREAMLIT_WORKFLOW_MUTATIONS_DISABLED", raising=False)
    ok_allowed = workflow_hooks.complete_letter_generation_step(
        1, wid, ["experian"], audit_source="api"
    )
    assert ok_allowed is True
    assert _step_status(fetch_steps(wid), "letter_generation") == "completed"
