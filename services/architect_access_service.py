"""
Admin-only architect access: seed real workflows/org state and issue a valid session token.

Guarded exclusively by ``WORKFLOW_ADMIN_API_SECRET`` at the HTTP layer (``require_admin_service``).
Uses WorkflowEngine + existing workflow hooks — no parallel progression system.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, List, Optional

import auth
from database import get_db
from services.org_program_session_service import (
    create_program_session,
    set_enrollment_session,
    update_program_session,
)
from services.org_program_workflow_service import advance_org_program_steps, ensure_org_program_workflow
from services.org_service import (
    add_organization_member,
    create_organization,
    get_organization,
)
from services.program_enrollment_service import create_program_enrollment, get_enrollment
from services.workflow import hooks as wf_hooks
from services.workflow import registry as reg
from services.workflow.engine import WorkflowEngine, compute_authoritative_step
from services.workflow.escalation_engine import recompute_escalation_for_workflow
from services.workflow.hooks import complete_letter_generation_step
from services.workflow.repository import ensure_active_workflow_id, merge_into_workflow_metadata
from services.workflow.workflow_db import get_workflow_db

_log = logging.getLogger(__name__)

FIXTURE_ORG_NAME = "850 Lab Architect Fixture Org"
ARCHITECT_AUDIT = "architect_access_seed"
EMAIL_DOMAIN = "850lab-architect.invalid"

# Stable fixture identities (one membership each; V1 one org per user).
USER_CONSUMER_PREFIX = f"architect.consumer"
USER_ORG_ADMIN = f"architect.org.admin@{EMAIL_DOMAIN}"
USER_ORG_INSTRUCTOR = f"architect.org.instructor@{EMAIL_DOMAIN}"
USER_ORG_PARTICIPANT = f"architect.org.participant@{EMAIL_DOMAIN}"


def _consumer_email(suffix: str) -> str:
    return f"{USER_CONSUMER_PREFIX}.{suffix}@{EMAIL_DOMAIN}"


def _verify_user_email(user_id: int) -> None:
    with get_db() as (conn, cur):
        cur.execute(
            "UPDATE users SET email_verified = TRUE WHERE id = %s",
            (user_id,),
        )
        conn.commit()


def _ensure_fixture_user(*, email: str, display_name: str, platform_role: str = "consumer") -> int:
    row = auth.get_user_by_email(email)
    if row:
        uid = int(row["id"])
        _verify_user_email(uid)
        return uid
    pw = secrets.token_urlsafe(24)
    created = auth.create_user(
        email,
        pw,
        display_name=display_name,
        role=platform_role,
    )
    if created.get("error"):
        raise RuntimeError(str(created.get("error")))
    uid = int(created["id"])
    _verify_user_email(uid)
    return uid


def _archive_consumer_workflows(user_id: int) -> None:
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            UPDATE workflow_sessions
            SET overall_status = 'completed',
                completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND workflow_type = %s
              AND overall_status IN ('active', 'failed')
            """,
            (user_id, reg.WORKFLOW_TYPE_DEFAULT),
        )
        conn.commit()


def _workflow_snapshot(wid: str) -> Dict[str, Any]:
    eng = WorkflowEngine()
    session, _, smap = eng.get_state_bundle(wid)
    if not session:
        return {"workflowId": wid, "currentStep": None, "linearPhase": "unknown", "overallStatus": None}
    order = reg.linear_order_for(str(session.get("workflow_type") or reg.WORKFLOW_TYPE_DEFAULT))
    head, phase = compute_authoritative_step(smap, order)
    return {
        "workflowId": wid,
        "currentStep": head,
        "linearPhase": phase,
        "overallStatus": session.get("overall_status"),
        "workflowType": session.get("workflow_type"),
    }


def _seed_consumer_through(
    user_id: int,
    *,
    stop_after: Optional[str] = None,
    wid: Optional[str] = None,
) -> str:
    """
    Advance consumer ``dispute_linear_v1`` using trusted hooks/engine.
    ``stop_after`` is a backend step_id after which we stop (that step remains the head if not completed).
    None = leave at upload (fresh session).
    """
    w = wid or ensure_active_workflow_id(user_id)
    rid = 850_000 + (user_id % 90_000)

    if stop_after is None or stop_after == "upload":
        return w

    wf_hooks.notify_upload_and_parse_success(
        user_id,
        rid,
        "equifax",
        "architect-seed.pdf",
        workflow_id=w,
    )

    if stop_after == "parse_analyze":
        return w

    wf_hooks.notify_review_claims_completed(
        user_id,
        workflow_id=w,
        item_count=3,
        audit_source=ARCHITECT_AUDIT,
    )
    if stop_after == "review_claims":
        return w

    wf_hooks.notify_select_disputes_completed(
        user_id,
        workflow_id=w,
        selected_count=3,
        bureaus=["Equifax", "Experian", "TransUnion"],
        audit_source=ARCHITECT_AUDIT,
    )
    if stop_after == "select_disputes":
        return w

    eng = WorkflowEngine()
    if not eng.service_complete_step(
        w,
        "payment",
        {"architectSeed": True, "source": ARCHITECT_AUDIT},
        audit_source=ARCHITECT_AUDIT,
        audit_user_id=user_id,
    ):
        _log.warning("architect: payment step not completed wf=%s", w)
    if stop_after == "payment":
        return w

    ok = complete_letter_generation_step(
        user_id,
        w,
        ["equifax", "experian", "transunion"],
        audit_source=ARCHITECT_AUDIT,
    )
    if not ok:
        _log.warning("architect: letter_generation not completed wf=%s", w)
    if stop_after == "letter_generation":
        return w

    if not eng.service_complete_step(
        w,
        "proof_attachment",
        {
            "hasGovernmentId": True,
            "hasAddressProof": True,
            "hasSignature": True,
            "source": ARCHITECT_AUDIT,
        },
        audit_source=ARCHITECT_AUDIT,
        audit_user_id=user_id,
    ):
        _log.warning("architect: proof_attachment not completed wf=%s", w)
    if stop_after == "proof_attachment":
        return w

    # Mail: partial sends until gate completes mail+track inside hook.
    for bureau, tn in (
        ("equifax", "ARCH-EFX-001"),
        ("experian", "ARCH-EXP-002"),
        ("transunion", "ARCH-TU-003"),
    ):
        wf_hooks.notify_certified_mail_sent(
            user_id,
            bureau,
            tn,
            lob_id=f"architect_{bureau}",
            workflow_id=w,
            report_id=rid,
        )
    if stop_after == "mail":
        return w

    return w


def _apply_escalation_metadata(wid: str) -> None:
    cid = "850architect-esc-claim-1"

    def _mut(meta: Dict[str, Any]) -> None:
        ds = meta.get("dispute_selection")
        if not isinstance(ds, dict):
            ds = {}
        else:
            ds = dict(ds)
        ds["cumulative_disputed_review_claim_ids"] = [cid]
        ds["claim_outcomes"] = {cid: "no_response"}
        meta["dispute_selection"] = ds

    merge_into_workflow_metadata(wid, _mut)
    recompute_escalation_for_workflow(wid)


def _ensure_fixture_org_id() -> int:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            "SELECT id FROM organizations WHERE name = %s LIMIT 1",
            (FIXTURE_ORG_NAME,),
        )
        row = cur.fetchone()
        if row:
            return int(row["id"])
    org = create_organization(FIXTURE_ORG_NAME, status="active")
    if org.get("error"):
        raise RuntimeError(str(org["error"]))
    return int(org["id"])


def _unlock_org_program_access(org_id: int) -> None:
    with get_db() as (conn, cur):
        cur.execute(
            """
            UPDATE organizations
            SET payment_access = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            ("full", org_id),
        )
        conn.commit()


def _ensure_org_role_user(org_id: int, email: str, display: str, org_role: str) -> int:
    uid = _ensure_fixture_user(email=email, display_name=display)
    m = auth.get_user_by_id(uid)
    if not m:
        raise RuntimeError("user missing after ensure")
    from services.org_service import get_active_membership_for_user

    existing = get_active_membership_for_user(uid)
    if existing:
        if int(existing["organization_id"]) != org_id:
            raise RuntimeError(
                f"Fixture user {email} already belongs to another org (V1 single-org)."
            )
        if str(existing.get("role")) != org_role:
            raise RuntimeError(
                f"Fixture user {email} has role {existing.get('role')}, expected {org_role}."
            )
        return uid
    allow_admin = org_role == "org_admin"
    res = add_organization_member(
        org_id,
        uid,
        org_role,
        allow_org_admin_seat=allow_admin,
    )
    if res.get("error"):
        raise RuntimeError(str(res["error"]))
    return uid


def _ensure_participant_enrollment(org_id: int, user_id: int) -> Dict[str, Any]:
    enr = get_enrollment(org_id, user_id)
    if enr:
        return enr
    row = create_program_enrollment(org_id, user_id, status="active")
    if row.get("error"):
        raise RuntimeError(str(row["error"]))
    return row


def list_scenarios() -> List[Dict[str, Any]]:
    """Static catalog for Mission Control UI."""
    return [
        {
            "id": "consumer_upload",
            "label": "Consumer · upload",
            "persona": "consumer",
            "launchPath": "/upload",
            "description": "Fresh dispute workflow at upload.",
            "fixtureHint": _consumer_email("upload"),
        },
        {
            "id": "consumer_prepare",
            "label": "Consumer · prepare (findings)",
            "persona": "consumer",
            "launchPath": "/prepare",
            "description": "After parse; head at review_claims.",
            "fixtureHint": _consumer_email("prepare"),
        },
        {
            "id": "consumer_strategy",
            "label": "Consumer · strategy",
            "persona": "consumer",
            "launchPath": "/strategy",
            "description": "Head at select_disputes.",
            "fixtureHint": _consumer_email("strategy"),
        },
        {
            "id": "consumer_payment",
            "label": "Consumer · payment",
            "persona": "consumer",
            "launchPath": "/payment",
            "description": "Head at payment.",
            "fixtureHint": _consumer_email("payment"),
        },
        {
            "id": "consumer_letters",
            "label": "Consumer · letters",
            "persona": "consumer",
            "launchPath": "/letters",
            "description": "Head at letter_generation.",
            "fixtureHint": _consumer_email("letters"),
        },
        {
            "id": "consumer_proof",
            "label": "Consumer · proof",
            "persona": "consumer",
            "launchPath": "/proof",
            "description": "Head at proof_attachment.",
            "fixtureHint": _consumer_email("proof"),
        },
        {
            "id": "consumer_send",
            "label": "Consumer · send (mail)",
            "persona": "consumer",
            "launchPath": "/send",
            "description": "Head at mail.",
            "fixtureHint": _consumer_email("send"),
        },
        {
            "id": "consumer_tracking",
            "label": "Consumer · tracking",
            "persona": "consumer",
            "launchPath": "/tracking",
            "description": "Completes mail+track via Lob hooks (may finish linear).",
            "fixtureHint": _consumer_email("tracking"),
        },
        {
            "id": "consumer_escalation",
            "label": "Consumer · escalation context",
            "persona": "consumer",
            "launchPath": "/escalation",
            "description": "After tracking seed; dispute_selection + recompute_escalation_for_workflow.",
            "fixtureHint": _consumer_email("escalation"),
        },
        {
            "id": "org_participant_upload",
            "label": "Org participant · program upload",
            "persona": "org_participant",
            "launchPath": "/program/upload",
            "description": "Unlocked org; org_program_v1 at orgprog_upload.",
        },
        {
            "id": "org_participant_letters",
            "label": "Org participant · program letters",
            "persona": "org_participant",
            "launchPath": "/program/letters",
            "description": "Advanced through orgprog_selections_saved.",
            "fixtureHint": f"{FIXTURE_ORG_NAME} · {USER_ORG_PARTICIPANT}",
        },
        {
            "id": "org_participant_mid_session",
            "label": "Org participant · mid workshop session",
            "persona": "org_participant",
            "launchPath": "/program/progress",
            "description": "Participant assigned to an active workshop session.",
            "fixtureHint": f"{FIXTURE_ORG_NAME} · {USER_ORG_PARTICIPANT}",
        },
        {
            "id": "org_instructor_desk",
            "label": "Org instructor · guide desk",
            "persona": "org_instructor",
            "launchPath": "/program/instructor",
            "description": "Instructor seat; active workshop session for fixture org.",
            "fixtureHint": f"{FIXTURE_ORG_NAME} · {USER_ORG_INSTRUCTOR}",
        },
        {
            "id": "org_admin_insights",
            "label": "Org admin · cohort overview",
            "persona": "org_admin",
            "launchPath": "/program/org-insights",
            "description": "Buyer/admin seat on fixture org.",
            "fixtureHint": f"{FIXTURE_ORG_NAME} · {USER_ORG_ADMIN}",
        },
    ]


def apply_scenario(
    scenario_id: str,
    *,
    reset_consumer_workflow: bool = True,
) -> Dict[str, Any]:
    sid = (scenario_id or "").strip()
    meta_by_id = {s["id"]: s for s in list_scenarios()}
    if sid not in meta_by_id:
        return {"ok": False, "error": {"code": "UNKNOWN_SCENARIO", "messageSafe": "Unknown scenario."}}

    launch = meta_by_id[sid]["launchPath"]
    persona = meta_by_id[sid]["persona"]

    org_id: Optional[int] = None
    membership_role: Optional[str] = None
    enrollment_id: Optional[int] = None
    program_workflow_id: Optional[str] = None
    consumer_wid: Optional[str] = None

    if persona == "consumer":
        consumer_emails = {
            "consumer_upload": _consumer_email("upload"),
            "consumer_prepare": _consumer_email("prepare"),
            "consumer_strategy": _consumer_email("strategy"),
            "consumer_payment": _consumer_email("payment"),
            "consumer_letters": _consumer_email("letters"),
            "consumer_proof": _consumer_email("proof"),
            "consumer_send": _consumer_email("send"),
            "consumer_tracking": _consumer_email("tracking"),
            "consumer_escalation": _consumer_email("escalation"),
        }
        email = consumer_emails[sid]
        uid = _ensure_fixture_user(email=email, display_name=f"Architect {sid}")
        if reset_consumer_workflow:
            _archive_consumer_workflows(uid)
        ensure_active_workflow_id(uid)
        stop_map = {
            "consumer_upload": None,
            "consumer_prepare": "review_claims",
            "consumer_strategy": "select_disputes",
            "consumer_payment": "payment",
            "consumer_letters": "letter_generation",
            "consumer_proof": "proof_attachment",
            # /send: mail step available (do not fire Lob hooks yet)
            "consumer_send": "proof_attachment",
            "consumer_tracking": "track",
            "consumer_escalation": "track",
        }
        consumer_wid = _seed_consumer_through(uid, stop_after=stop_map.get(sid))
        if sid == "consumer_escalation":
            _apply_escalation_metadata(consumer_wid)
        snap = _workflow_snapshot(consumer_wid)
        token = auth.create_session(uid)
        user_row = auth.get_user_by_id(uid)
        return {
            "ok": True,
            "scenarioId": sid,
            "sessionToken": token,
            "launchPath": launch,
            "fixtureHint": meta_by_id[sid].get("fixtureHint"),
            "user": {
                "id": uid,
                "email": user_row.get("email") if user_row else email,
                "displayName": (user_row or {}).get("display_name"),
                "platformRole": (user_row or {}).get("role"),
            },
            "persona": persona,
            "membershipRole": None,
            "organizationId": None,
            "enrollmentId": None,
            "programWorkflowId": None,
            "consumerWorkflow": snap,
        }

    org_id = _ensure_fixture_org_id()
    _unlock_org_program_access(org_id)

    if persona == "org_admin":
        uid = _ensure_org_role_user(
            org_id,
            USER_ORG_ADMIN,
            "Architect Org Admin",
            "org_admin",
        )
        token = auth.create_session(uid)
        user_row = auth.get_user_by_id(uid)
        return {
            "ok": True,
            "sessionToken": token,
            "launchPath": launch,
            "user": {
                "id": uid,
                "email": user_row.get("email"),
                "displayName": user_row.get("display_name"),
                "platformRole": user_row.get("role"),
            },
            "persona": persona,
            "membershipRole": "org_admin",
            "organizationId": org_id,
            "enrollmentId": None,
            "programWorkflowId": None,
            "consumerWorkflow": None,
        }

    if persona == "org_instructor":
        uid = _ensure_org_role_user(
            org_id,
            USER_ORG_INSTRUCTOR,
            "Architect Instructor",
            "org_instructor",
        )
        # Active workshop for desk UX
        sess = create_program_session(org_id, "Architect fixture — live room")
        if sess.get("error"):
            raise RuntimeError(str(sess["error"]))
        session_row = update_program_session(org_id, int(sess["id"]), state="active")
        if session_row.get("error"):
            raise RuntimeError(str(session_row["error"]))
        # Attach participant to same session if present
        p_uid = _ensure_fixture_user(
            email=USER_ORG_PARTICIPANT,
            display_name="Architect Participant",
        )
        _ensure_org_role_user(
            org_id,
            USER_ORG_PARTICIPANT,
            "Architect Participant",
            "org_user",
        )
        enr_row = _ensure_participant_enrollment(org_id, p_uid)
        eid = int(enr_row["id"])
        set_enrollment_session(org_id, eid, int(sess["id"]))

        token = auth.create_session(uid)
        user_row = auth.get_user_by_id(uid)
        return {
            "ok": True,
            "scenarioId": sid,
            "sessionToken": token,
            "launchPath": launch,
            "fixtureHint": meta_by_id[sid].get("fixtureHint"),
            "user": {
                "id": uid,
                "email": user_row.get("email"),
                "displayName": user_row.get("display_name"),
                "platformRole": user_row.get("role"),
            },
            "persona": persona,
            "membershipRole": "org_instructor",
            "organizationId": org_id,
            "enrollmentId": eid,
            "programWorkflowId": None,
            "workshopSessionId": int(sess["id"]),
            "consumerWorkflow": None,
        }

    if persona == "org_participant":
        uid = _ensure_fixture_user(
            email=USER_ORG_PARTICIPANT,
            display_name="Architect Participant",
        )
        _ensure_org_role_user(org_id, USER_ORG_PARTICIPANT, "Architect Participant", "org_user")
        enr = _ensure_participant_enrollment(org_id, uid)
        enrollment_id = int(enr["id"])
        program_workflow_id = ensure_org_program_workflow(uid, org_id, enrollment_id)

        if sid == "org_participant_letters":
            advance_org_program_steps(
                uid,
                org_id,
                enrollment_id,
                ["orgprog_upload", "orgprog_findings_ready", "orgprog_selections_saved"],
                audit_source=ARCHITECT_AUDIT,
            )
        elif sid == "org_participant_mid_session":
            sess = create_program_session(org_id, "Architect fixture — cohort session")
            if sess.get("error"):
                raise RuntimeError(str(sess["error"]))
            update_program_session(org_id, int(sess["id"]), state="active")
            set_enrollment_session(org_id, enrollment_id, int(sess["id"]))

        snap = _workflow_snapshot(program_workflow_id)
        token = auth.create_session(uid)
        user_row = auth.get_user_by_id(uid)
        return {
            "ok": True,
            "scenarioId": sid,
            "sessionToken": token,
            "launchPath": launch,
            "fixtureHint": meta_by_id[sid].get("fixtureHint"),
            "user": {
                "id": uid,
                "email": user_row.get("email"),
                "displayName": user_row.get("display_name"),
                "platformRole": user_row.get("role"),
            },
            "persona": persona,
            "membershipRole": "org_user",
            "organizationId": org_id,
            "enrollmentId": enrollment_id,
            "programWorkflowId": program_workflow_id,
            "consumerWorkflow": snap,
        }

    return {"ok": False, "error": {"code": "UNSUPPORTED", "messageSafe": "Unsupported persona."}}
