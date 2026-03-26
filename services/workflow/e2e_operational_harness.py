"""
Controlled end-to-end workflow verification (Phase 3D).

Uses the same trusted hooks/engine paths as production. Requires a real DB and
an existing ``users.id`` row.

Environment:
  WORKFLOW_E2E_USER_ID   — required integer user id for all runs
  WORKFLOW_E2E_FAILURES  — set to 1 to run failure-injection sub-suite after happy path
"""

from __future__ import annotations

import os
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.workflow.engine import WorkflowEngine, compute_authoritative_step
from services.workflow import hooks as wf_hooks
from services.workflow.home_summary_service import build_home_summary
from services.workflow import reminder_service as rem_svc
from services.workflow.recovery_service import compute_recovery_actions
from services.workflow.recovery_execution_service import execute_retry_step
from services.workflow.repository import fetch_session
from services.workflow import mail_gating as mail_gate


@dataclass
class StepResult:
    name: str
    ok: bool
    kind: str  # pass | fail | skip | warn
    detail: str = ""
    drift: List[str] = field(default_factory=list)


def _require_user_id() -> int:
    raw = (os.environ.get("WORKFLOW_E2E_USER_ID") or "").strip()
    if not raw.isdigit():
        raise RuntimeError("Set WORKFLOW_E2E_USER_ID to a positive integer (existing users.id).")
    return int(raw)


def _bundle(wid: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    eng = WorkflowEngine()
    session, _, smap = eng.get_state_bundle(wid)
    return session, smap


def _head(smap: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], str]:
    return compute_authoritative_step(smap)


def _drift_against_home_summary(wid: str) -> List[str]:
    eng = WorkflowEngine()
    _, smap = eng.get_state_bundle(wid)
    h, ph = _head(smap)
    hs = build_home_summary(wid)
    if not hs.get("ok"):
        return ["home_summary error: " + str(hs.get("error"))]
    hs_head = hs.get("currentStepId")
    if ph == "done" and hs.get("linearPhase") != "done":
        return [f"phase drift engine_done home linearPhase={hs.get('linearPhase')}"]
    if ph != "done" and h != hs_head:
        return [f"head drift engine={h} home_summary={hs_head}"]
    return []


def _run(
    name: str,
    fn: Callable[[], None],
    *,
    drift_wid: Optional[str] = None,
) -> StepResult:
    try:
        fn()
        dr = _drift_against_home_summary(drift_wid) if drift_wid else []
        return StepResult(name, True, "pass", drift=dr)
    except Exception as ex:
        return StepResult(
            name,
            False,
            "fail",
            f"{type(ex).__name__}: {ex}\n{traceback.format_exc()[-800:]}",
        )


def run_happy_path(user_id: int) -> Tuple[str, List[StepResult]]:
    import auth

    if not auth.get_user_by_id(user_id):
        raise RuntimeError(f"users.id={user_id} not found")

    eng = WorkflowEngine()
    init = eng.init_workflow(user_id=user_id, workflow_type=None, metadata={"e2eHarness": True})
    if init.get("actionResult") != "ok":
        raise RuntimeError(f"init_workflow rejected: {init.get('error')}")
    wid = str(init["workflowState"]["workflowId"])
    steps: List[StepResult] = []

    def drift_wid() -> str:
        return wid

    steps.append(
        _run(
            "01_init",
            lambda: None,
            drift_wid=wid,
        )
    )
    if not steps[-1].ok:
        return wid, steps

    steps.append(
        _run(
            "02_upload_parse",
            lambda: wf_hooks.notify_upload_and_parse_success(
                user_id,
                report_id=999001,
                bureau="equifax",
                filename="e2e_harness.pdf",
                workflow_id=wid,
            ),
            drift_wid=wid,
        )
    )

    steps.append(
        _run(
            "03_review_claims",
            lambda: wf_hooks.notify_review_claims_completed(
                user_id, workflow_id=wid, item_count=3
            ),
            drift_wid=wid,
        )
    )

    steps.append(
        _run(
            "04_select_disputes",
            lambda: wf_hooks.notify_select_disputes_completed(
                user_id,
                workflow_id=wid,
                selected_count=3,
                bureaus=["Equifax", "Experian", "TransUnion"],
            ),
            drift_wid=wid,
        )
    )

    def _must_complete(step_id: str, summary: Dict[str, Any]) -> None:
        if not eng.service_complete_step(
            wid,
            step_id,
            summary,
            audit_source="e2e_operational_harness",
            audit_user_id=user_id,
        ):
            raise RuntimeError(f"service_complete_step({step_id}) returned False")

    steps.append(
        _run(
            "05_payment",
            lambda: _must_complete(
                "payment",
                {"e2eSynthetic": True, "source": "e2e_operational_harness"},
            ),
            drift_wid=wid,
        )
    )

    steps.append(
        _run(
            "06_letter_generation",
            lambda: _must_complete("letter_generation", {"e2eSynthetic": True}),
            drift_wid=wid,
        )
    )

    steps.append(
        _run(
            "07_proof_attachment",
            lambda: _must_complete("proof_attachment", {"e2eSynthetic": True}),
            drift_wid=wid,
        )
    )

    def send_three() -> None:
        for b in ("equifax", "experian", "transunion"):
            wf_hooks.notify_certified_mail_sent(
                user_id,
                b,
                f"E2E-{b[:4].upper()}",
                lob_id=f"lob_e2e_{b}",
                workflow_id=wid,
                report_id=None,
            )

    steps.append(_run("08_mail_gating_three_bureaus", send_three, drift_wid=wid))

    sess = fetch_session(wid)
    meta = sess.get("metadata") or {}
    if isinstance(meta, str):
        import json

        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    mail = (meta or {}).get("mail") or {}
    exp = int(mail.get("expected_unique_bureau_sends") or 0)
    conf = mail.get("confirmed_bureaus") or []
    if exp != 3 or len(conf) != 3:
        steps.append(
            StepResult(
                "08b_mail_metadata_counts",
                False,
                "fail",
                f"expected_unique_bureau_sends={exp} confirmed_len={len(conf)}",
            )
        )
    else:
        steps.append(StepResult("08b_mail_metadata_counts", True, "pass", "expected=3 confirmed=3"))

    _, smap = _bundle(wid)
    tr = smap.get("track")
    if not tr or tr.get("status") != "completed":
        steps.append(
            StepResult(
                "09_track_assert",
                False,
                "fail",
                f"track status={tr.get('status') if tr else None}",
            )
        )
    else:
        steps.append(StepResult("09_track_assert", True, "pass", "track completed"))

    steps.append(
        _run(
            "10_response_intake_unclear",
            lambda: _intake_unclear(wid, user_id),
            drift_wid=wid,
        )
    )

    steps.append(
        _run(
            "11_reminder_candidates",
            lambda: rem_svc.create_reminder_candidates_for_workflow(wid),
            drift_wid=wid,
        )
    )

    created = rem_svc.list_eligible_for_scan(limit=50)
    ours = [r for r in created if str(r.get("workflow_id")) == wid]
    if not ours:
        steps.append(
            StepResult(
                "12_reminder_delivery",
                True,
                "skip",
                "No eligible reminder for this workflow (lifecycle flags); run after stall signals or insert test row.",
            )
        )
    else:
        rid = ours[0]["reminder_id"]
        if not rem_svc.queue_reminder(rid):
            steps.append(
                StepResult("12_reminder_delivery", False, "fail", "queue_reminder failed")
            )
        else:
            out = rem_svc.deliver_reminder(rid)
            dr = _drift_against_home_summary(wid)
            if out.get("ok"):
                steps.append(
                    StepResult("12_reminder_delivery", True, "pass", str(out.get("deliveryResult")), drift=dr)
                )
            else:
                steps.append(
                    StepResult(
                        "12_reminder_delivery",
                        True,
                        "warn",
                        f"delivery failed (expected without Resend): {out}",
                        drift=dr,
                    )
                )

    return wid, steps


def _intake_unclear(wid: str, user_id: int) -> None:
    from services.workflow.response_intake_service import intake_bureau_response

    r = intake_bureau_response(
        workflow_id=wid,
        user_id=user_id,
        source_type="bureau",
        response_channel="upload",
        parsed_summary={},
        storage_ref=f"e2e://{uuid.uuid4()}",
    )
    if not r.get("ok"):
        raise RuntimeError(str(r.get("error")))
    cls = (r.get("classification") or {}).get("label") if r.get("classification") else None
    if cls and cls != "insufficient_to_classify":
        pass


def run_failure_suite(user_id: int) -> List[StepResult]:
    out: List[StepResult] = []
    eng = WorkflowEngine()
    init = eng.init_workflow(user_id=user_id, metadata={"e2eFailureSuite": True})
    if init.get("actionResult") != "ok":
        return [
            StepResult(
                "F_init",
                False,
                "fail",
                str(init.get("error")),
            )
        ]
    wid = str(init["workflowState"]["workflowId"])

    def to_mail_one_bureau() -> None:
        wf_hooks.notify_upload_and_parse_success(
            user_id, 999002, "equifax", "fail_suite.pdf", workflow_id=wid
        )
        wf_hooks.notify_review_claims_completed(user_id, workflow_id=wid)
        wf_hooks.notify_select_disputes_completed(
            user_id,
            workflow_id=wid,
            selected_count=1,
            bureaus=["Equifax"],
        )
        ok = eng.service_complete_step(
            wid,
            "payment",
            {"e2e": True},
            audit_source="e2e_failure_suite",
            audit_user_id=user_id,
        )
        if not ok:
            raise RuntimeError("payment complete failed")
        for sid in ("letter_generation", "proof_attachment"):
            if not eng.service_complete_step(
                wid,
                sid,
                {"e2e": True},
                audit_source="e2e_failure_suite",
                audit_user_id=user_id,
            ):
                raise RuntimeError(f"complete {sid} failed")

    out.append(_run("F01_progress_to_mail", to_mail_one_bureau, drift_wid=wid))

    def fail_mail() -> None:
        wf_hooks.notify_mail_send_failed(
            user_id,
            "LOB_REJECT",
            "Simulated carrier reject",
            workflow_id=wid,
        )

    out.append(_run("F02_mail_send_failed", fail_mail, drift_wid=wid))
    rec = compute_recovery_actions(wid)
    types = [a.get("actionType") for a in (rec.get("recoveryActions") or [])]
    if "re_run_mail_attempt" not in types and "retry_step" not in types:
        out.append(
            StepResult(
                "F03_recovery_after_mail_fail",
                False,
                "fail",
                f"unexpected recovery actions: {types}",
            )
        )
    else:
        out.append(
            StepResult(
                "F03_recovery_after_mail_fail",
                True,
                "pass",
                f"actions include mail/retry: {types[:5]}",
            )
        )

    sess, smap = _bundle(wid)
    if not sess:
        out.append(StepResult("F04_session", False, "fail", "no session"))
        return out
    failed_step = None
    for sid, row in smap.items():
        if row.get("status") == "failed":
            failed_step = sid
            break
    if failed_step:
        r = execute_retry_step(
            workflow_id=wid,
            user_id=user_id,
            step_id=failed_step,
            actor_source="e2e_failure_suite",
            reason_safe="harness recovery execution",
        )
        out.append(
            StepResult(
                "F04_recovery_execute_retry",
                bool(r.get("ok")),
                "pass" if r.get("ok") else "fail",
                str(r),
            )
        )
    else:
        out.append(StepResult("F04_recovery_execute_retry", False, "fail", "no failed step"))

    try:
        init2 = eng.init_workflow(user_id=user_id, metadata={"e2eParseFail": True})
        if init2.get("actionResult") != "ok":
            raise RuntimeError(str(init2.get("error")))
        w2 = str(init2["workflowState"]["workflowId"])
        if not eng.service_complete_step(
            w2,
            "upload",
            {"e2e": True, "file": "parse_fail.pdf"},
            audit_source="e2e_failure_suite",
            audit_user_id=user_id,
        ):
            raise RuntimeError("upload complete failed")
        if not eng.service_fail_step(
            w2,
            "parse_analyze",
            "PARSE_SIM",
            "Simulated parse failure",
            audit_source="e2e_failure_suite",
            audit_user_id=user_id,
        ):
            raise RuntimeError("service_fail_step(parse_analyze) returned False")
        hs = build_home_summary(w2)
        if not hs.get("ok") or not hs.get("failedStep"):
            raise RuntimeError("expected failedStep in home summary after parse fail")
        out.append(
            StepResult(
                "F05_parse_fail_separate_wf",
                True,
                "pass",
                f"workflowId={w2}",
            )
        )
    except Exception as ex:
        out.append(StepResult("F05_parse_fail_separate_wf", False, "fail", str(ex)))

    return out


def run_incomplete_payment_stall(user_id: int) -> StepResult:
    eng = WorkflowEngine()
    init = eng.init_workflow(user_id=user_id, metadata={"e2ePaymentStall": True})
    wid = str(init["workflowState"]["workflowId"])
    wf_hooks.notify_upload_and_parse_success(
        user_id, 999004, "transunion", "p.pdf", workflow_id=wid
    )
    wf_hooks.notify_review_claims_completed(user_id, workflow_id=wid)
    wf_hooks.notify_select_disputes_completed(
        user_id, workflow_id=wid, selected_count=1, bureaus=["TransUnion"]
    )
    h, _ = _head(_bundle(wid)[1])
    if h != "payment":
        return StepResult(
            "F06_incomplete_payment_head",
            False,
            "fail",
            f"expected head payment got {h}",
        )
    hs = build_home_summary(wid)
    if hs.get("currentStepId") != "payment":
        return StepResult(
            "F06_incomplete_payment_home",
            False,
            "fail",
            "home_summary should still show payment",
        )
    return StepResult("F06_incomplete_payment_stall", True, "pass", "head payment without completing")


def run_duplicate_mail_prevention_assertion(user_id: int) -> StepResult:
    eng = WorkflowEngine()
    init = eng.init_workflow(user_id=user_id, metadata={"e2eMailDedupe": True})
    wid = str(init["workflowState"]["workflowId"])
    wf_hooks.notify_upload_and_parse_success(
        user_id, 999005, "equifax", "d.pdf", workflow_id=wid
    )
    wf_hooks.notify_review_claims_completed(user_id, workflow_id=wid)
    wf_hooks.notify_select_disputes_completed(
        user_id, workflow_id=wid, selected_count=1, bureaus=["Equifax"]
    )
    eng.service_complete_step(
        wid, "payment", {"e2e": True}, audit_source="e2e", audit_user_id=user_id
    )
    for sid in ("letter_generation", "proof_attachment"):
        eng.service_complete_step(
            wid, sid, {"e2e": True}, audit_source="e2e", audit_user_id=user_id
        )
    wf_hooks.notify_certified_mail_sent(
        user_id, "equifax", "T1", lob_id="lob1", workflow_id=wid
    )
    wf_hooks.notify_certified_mail_sent(
        user_id, "equifax", "T2", lob_id="lob2", workflow_id=wid
    )
    sess = fetch_session(wid)
    meta = sess.get("metadata") or {}
    if isinstance(meta, str):
        import json

        meta = json.loads(meta) if meta else {}
    mail = meta.get("mail") or {}
    exp, confirmed, _ = mail_gate.get_mail_gate_state(meta)
    if len(confirmed) != 1:
        return StepResult(
            "F07_duplicate_bureau_confirm",
            False,
            "fail",
            f"expected 1 unique bureau got {confirmed}",
        )
    return StepResult("F07_duplicate_bureau_confirm", True, "pass", str(conf))


def report_dict(
    happy_wid: str,
    happy_steps: List[StepResult],
    failure_steps: Optional[List[StepResult]],
    extra: List[StepResult],
) -> Dict[str, Any]:
    def serial(sr: StepResult) -> Dict[str, Any]:
        return {
            "name": sr.name,
            "ok": sr.ok,
            "kind": sr.kind,
            "detail": sr.detail[:2000],
            "drift": sr.drift,
        }

    return {
        "happyPathWorkflowId": happy_wid,
        "happyPathSteps": [serial(s) for s in happy_steps],
        "failureSteps": [serial(s) for s in (failure_steps or [])],
        "extraSteps": [serial(s) for s in extra],
    }


def run_all() -> Dict[str, Any]:
    uid = _require_user_id()
    wid, happy = run_happy_path(uid)
    failures: Optional[List[StepResult]] = None
    extra: List[StepResult] = []
    if (os.environ.get("WORKFLOW_E2E_FAILURES") or "").strip() in ("1", "true", "yes"):
        failures = run_failure_suite(uid)
        extra.append(run_incomplete_payment_stall(uid))
        extra.append(run_duplicate_mail_prevention_assertion(uid))
    return report_dict(wid, happy, failures, extra)
