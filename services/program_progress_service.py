"""
Org program **delivery / instructor / reporting** layer around the single workflow engine.

**Authoritative progression** (current head, completed steps, next actions) lives only in
``workflow_sessions`` + ``workflow_steps``, mutated exclusively via
``WorkflowEngine.service_complete_step`` (and engine internals). Clients must use
``canonicalProgression`` from ``services.workflow.progression_api`` for that truth.

This module:

* Ensures a projection row exists on ``organization_program_progress`` for UX and S5B.
* Mirrors engine completion times into that row when ``program_workflow_id`` is bound.
* Exposes **milestone-shaped** summaries (``systemState``, ``effectiveState``, gates) for
  delivery gating and instructor pause/advance/reset **overlay**. Those fields are **not**
  a second progression engine; they do not replace ``canonicalProgression``.
* **Instructor ``advance``** (``apply_instructor_program_override``) updates the overlay row
  and **also** completes the corresponding ``orgprog_*`` steps via
  ``advance_org_program_steps`` so the engine stays the write authority.
* **Instructor ``reset``** only adjusts overlay flags for gating; it does **not** rewind
  ``workflow_steps`` (no engine reset API in this slice). Canonical head may remain ahead
  of ``effectiveState`` until the participant catches up in-product.

Legacy: if no ``program_workflow_id`` exists after ``ensure_org_program_workflow`` fails,
milestone timestamps may be **inferred from reports** — projection only, never engine
authority.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from database import get_db

from services.me_org_report_service import build_findings_payload
from services.program_enrollment_service import get_program_workflow_id_for_enrollment
from services.workflow.repository import fetch_steps

_log = logging.getLogger(__name__)

PROGRAM_STEPS: Tuple[str, ...] = (
    "enrollment",
    "upload",
    "findings_ready",
    "selections_saved",
    "letters_generated",
)

_STEP_INDEX = {name: i for i, name in enumerate(PROGRAM_STEPS)}

# Maps coarse PROGRAM_STEPS labels to org_program_v1 linear step ids (engine authority).
_MILESTONE_TO_ORG_STEP_ID: Dict[str, str] = {
    "enrollment": "orgprog_enrollment",
    "upload": "orgprog_upload",
    "findings_ready": "orgprog_findings_ready",
    "selections_saved": "orgprog_selections_saved",
    "letters_generated": "orgprog_letters_generated",
}


def orgprog_step_ids_through_milestone(target_step: str) -> List[str]:
    """Ordered ``orgprog_*`` ids from enrollment through ``target_step`` (inclusive)."""
    idx = step_index(target_step)
    if idx is None:
        return []
    out: List[str] = []
    for i in range(0, idx + 1):
        name = PROGRAM_STEPS[i]
        oid = _MILESTONE_TO_ORG_STEP_ID.get(name)
        if oid:
            out.append(oid)
    return out


def step_index(name: str) -> Optional[int]:
    return _STEP_INDEX.get(name)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return dict(row) if row else {}


def _progress_select_columns() -> str:
    return """
            id, organization_program_enrollment_id, user_id,
            upload_completed_at, findings_ready_at, selections_saved_at,
            letters_generated_at,
            instructor_paused, instructor_override_kind, instructor_override_step,
            instructor_override_at, instructor_override_by_user_id,
            instructor_override_reason_safe,
            created_at, updated_at
    """


def _organization_id_for_enrollment(enrollment_id: int) -> Optional[int]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT organization_id
            FROM organization_program_enrollments
            WHERE id = %s
            """,
            (enrollment_id,),
        )
        r = cur.fetchone()
    if not r:
        return None
    return int(r["organization_id"])


def ensure_program_progress_row(enrollment_id: int, user_id: int) -> Dict[str, Any]:
    """Insert progress row if missing; return current row."""
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO organization_program_progress (
                organization_program_enrollment_id, user_id
            )
            VALUES (%s, %s)
            ON CONFLICT (organization_program_enrollment_id) DO NOTHING
            """,
            (enrollment_id, user_id),
        )
        conn.commit()
        cur.execute(
            f"""
            SELECT {_progress_select_columns()}
            FROM organization_program_progress
            WHERE organization_program_enrollment_id = %s
            """,
            (enrollment_id,),
        )
        return _row_to_dict(cur.fetchone())


def initialize_progress_for_enrollment(enrollment_id: int, user_id: int) -> None:
    try:
        ensure_program_progress_row(enrollment_id, user_id)
    except Exception:
        _log.warning(
            "initialize_progress_for_enrollment failed eid=%s uid=%s",
            enrollment_id,
            user_id,
            exc_info=True,
        )


def _derive_upload_done(user_id: int, enrollment_id: int) -> bool:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT 1 FROM reports
            WHERE user_id = %s AND organization_program_enrollment_id = %s
            LIMIT 1
            """,
            (user_id, enrollment_id),
        )
        return cur.fetchone() is not None


def _derive_findings_ready(user_id: int, enrollment_id: int) -> bool:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id FROM reports
            WHERE user_id = %s AND organization_program_enrollment_id = %s
            ORDER BY upload_date DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (user_id, enrollment_id),
        )
        r = cur.fetchone()
    if not r:
        return False
    rid = int(r["id"])
    payload = build_findings_payload(user_id, report_id=rid)
    return payload.get("processingStatus") == "complete"


def _derive_selections_saved(user_id: int, enrollment_id: int) -> bool:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT 1
            FROM organization_program_dispute_selections s
            JOIN reports r ON r.id = s.report_id
            WHERE s.user_id = %s
              AND r.organization_program_enrollment_id = %s
              AND COALESCE(jsonb_array_length(s.selected_review_claim_ids), 0) > 0
            LIMIT 1
            """,
            (user_id, enrollment_id),
        )
        return cur.fetchone() is not None


def _derive_letters_generated(user_id: int, enrollment_id: int) -> bool:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT 1
            FROM letters l
            JOIN reports r ON r.id = l.report_id
            WHERE r.user_id = %s AND r.organization_program_enrollment_id = %s
            LIMIT 1
            """,
            (user_id, enrollment_id),
        )
        return cur.fetchone() is not None


def _sync_milestones_from_derived(
    enrollment_id: int,
    user_id: int,
    row: Dict[str, Any],
    d_upload: bool,
    d_findings: bool,
    d_sel: bool,
    d_letters: bool,
) -> Dict[str, Any]:
    """
    **Non-authoritative:** backfills projection timestamps from report heuristics when no
    program workflow id is available. Does **not** write ``workflow_steps``.
    """
    sets: List[str] = []
    if d_upload and not row.get("upload_completed_at"):
        sets.append(
            "upload_completed_at = COALESCE(upload_completed_at, CURRENT_TIMESTAMP)"
        )
    if d_findings and not row.get("findings_ready_at"):
        sets.append(
            "findings_ready_at = COALESCE(findings_ready_at, CURRENT_TIMESTAMP)"
        )
    if d_sel and not row.get("selections_saved_at"):
        sets.append(
            "selections_saved_at = COALESCE(selections_saved_at, CURRENT_TIMESTAMP)"
        )
    if d_letters and not row.get("letters_generated_at"):
        sets.append(
            "letters_generated_at = COALESCE(letters_generated_at, CURRENT_TIMESTAMP)"
        )
    if not sets:
        return row
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            f"""
            UPDATE organization_program_progress
            SET {", ".join(sets)}, updated_at = CURRENT_TIMESTAMP
            WHERE organization_program_enrollment_id = %s
            RETURNING {_progress_select_columns()}
            """,
            (enrollment_id,),
        )
        out = _row_to_dict(cur.fetchone())
        conn.commit()
    return out or row


def _milestone_flags(
    row: Dict[str, Any],
    d_upload: bool,
    d_findings: bool,
    d_sel: bool,
    d_letters: bool,
) -> Dict[str, bool]:
    return {
        "enrollment": True,
        "upload": bool(row.get("upload_completed_at")) or d_upload,
        "findings_ready": bool(row.get("findings_ready_at")) or d_findings,
        "selections_saved": bool(row.get("selections_saved_at")) or d_sel,
        "letters_generated": bool(row.get("letters_generated_at")) or d_letters,
    }


def _completed_and_next(flags: Dict[str, bool]) -> Tuple[List[str], Optional[str], str]:
    completed: List[str] = []
    for step in PROGRAM_STEPS:
        if flags.get(step):
            completed.append(step)
            continue
        return completed, step, step
    return completed, None, "letters_generated"


def build_effective_milestone_flags(
    system_flags: Dict[str, bool], row: Dict[str, Any]
) -> Dict[str, bool]:
    """
    Merge system milestones with instructor override (S5B).

    * reset → force later steps false (hold back).
    * advance → force steps up to target true (waive missing system milestones).
    """
    ef = dict(system_flags)
    if row.get("instructor_paused"):
        return ef
    kind = (row.get("instructor_override_kind") or "").strip() or None
    step = (row.get("instructor_override_step") or "").strip() or None
    if not kind or not step:
        return ef
    idx = step_index(step)
    if idx is None:
        return ef
    if kind == "reset":
        for i, name in enumerate(PROGRAM_STEPS):
            if i > idx:
                ef[name] = False
    elif kind == "advance":
        for i, name in enumerate(PROGRAM_STEPS):
            if i >= 1 and i <= idx:
                ef[name] = True
    return ef


def _instructor_state_public(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "paused": bool(row.get("instructor_paused")),
        "overrideKind": row.get("instructor_override_kind"),
        "overrideStep": row.get("instructor_override_step"),
        "overrideAt": row.get("instructor_override_at"),
        "overrideByUserId": row.get("instructor_override_by_user_id"),
        "overrideReasonSafe": row.get("instructor_override_reason_safe"),
    }


def _org_workflow_flags_from_steps(smap: Dict[str, Any]) -> Dict[str, bool]:
    """Map org_program_v1 step rows to PROGRAM_STEPS-style flags."""

    def done(sid: str) -> bool:
        r = smap.get(sid) or {}
        return str(r.get("status") or "") == "completed"

    return {
        "enrollment": done("orgprog_enrollment"),
        "upload": done("orgprog_upload"),
        "findings_ready": done("orgprog_findings_ready"),
        "selections_saved": done("orgprog_selections_saved"),
        "letters_generated": done("orgprog_letters_generated"),
    }


def sync_org_progress_row_from_org_workflow(
    enrollment_id: int, user_id: int, workflow_id: str
) -> None:
    """Mirror ``workflow_steps`` completion times into ``organization_program_progress`` (non-authoritative cache)."""
    rows = fetch_steps(workflow_id)
    smap = {str(r["step_id"]): r for r in rows}

    def ts(sid: str):
        r = smap.get(sid)
        if not r:
            return None
        return r.get("completed_at")

    ensure_program_progress_row(enrollment_id, user_id)
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            UPDATE organization_program_progress
            SET upload_completed_at = COALESCE(upload_completed_at, %s),
                findings_ready_at = COALESCE(findings_ready_at, %s),
                selections_saved_at = COALESCE(selections_saved_at, %s),
                letters_generated_at = COALESCE(letters_generated_at, %s),
                updated_at = CURRENT_TIMESTAMP
            WHERE organization_program_enrollment_id = %s
            """,
            (
                ts("orgprog_upload"),
                ts("orgprog_findings_ready"),
                ts("orgprog_selections_saved"),
                ts("orgprog_letters_generated"),
                enrollment_id,
            ),
        )
        conn.commit()


def refresh_program_progress(user_id: int, enrollment_id: int) -> Dict[str, Any]:
    row = ensure_program_progress_row(enrollment_id, user_id)
    org_id = _organization_id_for_enrollment(enrollment_id)
    if org_id is not None:
        try:
            from services.org_program_workflow_service import ensure_org_program_workflow

            ensure_org_program_workflow(user_id, org_id, enrollment_id)
        except Exception:
            _log.warning(
                "ensure_org_program_workflow failed during refresh eid=%s uid=%s",
                enrollment_id,
                user_id,
                exc_info=True,
            )
    wid = get_program_workflow_id_for_enrollment(enrollment_id)
    if wid:
        steps = fetch_steps(wid)
        smap = {str(s["step_id"]): s for s in steps}
        flags = _org_workflow_flags_from_steps(smap)
        sync_org_progress_row_from_org_workflow(enrollment_id, user_id, wid)
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"""
                SELECT {_progress_select_columns()}
                FROM organization_program_progress
                WHERE organization_program_enrollment_id = %s
                """,
                (enrollment_id,),
            )
            row = _row_to_dict(cur.fetchone()) or row
        return {
            "row": row,
            "flags": flags,
            "legacy_report_derived_projection": False,
        }

    _log.warning(
        "org program progress: no program_workflow_id after ensure; "
        "using legacy report-derived milestones eid=%s uid=%s",
        enrollment_id,
        user_id,
    )
    d_upload = _derive_upload_done(user_id, enrollment_id)
    d_findings = _derive_findings_ready(user_id, enrollment_id)
    d_sel = _derive_selections_saved(user_id, enrollment_id)
    d_letters = _derive_letters_generated(user_id, enrollment_id)
    row = _sync_milestones_from_derived(
        enrollment_id, user_id, row, d_upload, d_findings, d_sel, d_letters
    )
    flags = _milestone_flags(row, d_upload, d_findings, d_sel, d_letters)
    return {
        "row": row,
        "flags": flags,
        "legacy_report_derived_projection": True,
    }


def build_me_program_progress_payload(user_id: int, enrollment_id: int) -> Dict[str, Any]:
    state = refresh_program_progress(user_id, enrollment_id)
    row = state["row"]
    sys_flags = state["flags"]
    legacy_proj = bool(state.get("legacy_report_derived_projection"))
    sys_completed, sys_next, sys_current = _completed_and_next(sys_flags)
    ef = build_effective_milestone_flags(sys_flags, row)
    eff_completed, eff_next, eff_current = _completed_and_next(ef)
    paused = bool(row.get("instructor_paused"))
    return {
        "organizationProgramEnrollmentId": enrollment_id,
        "progressionReadContract": {
            "authoritativeField": "canonicalProgression",
            "milestoneFieldsRole": "delivery_gating_and_instructor_overlay",
            "rootMilestoneCurrentStepIsNotEngineHead": True,
            "legacyReportDerivedProjection": legacy_proj,
        },
        "systemState": {
            "currentStep": sys_current,
            "nextStep": sys_next,
            "completedSteps": sys_completed,
        },
        "instructorState": _instructor_state_public(row),
        "effectiveState": {
            "currentStep": "paused" if paused else eff_current,
            "nextStep": None if paused else eff_next,
            "completedSteps": eff_completed,
        },
        "currentStep": "paused" if paused else eff_current,
        "nextStep": None if paused else eff_next,
        "completedSteps": eff_completed,
        "stepTimestamps": {
            "uploadCompletedAt": row.get("upload_completed_at"),
            "findingsReadyAt": row.get("findings_ready_at"),
            "selectionsSavedAt": row.get("selections_saved_at"),
            "lettersGeneratedAt": row.get("letters_generated_at"),
        },
        "gates": {
            "mayUploadReport": (not paused) and ef["enrollment"],
            "mayAnalyzeReport": (not paused) and ef["upload"],
            "mayUseDisputeFlow": (not paused) and ef["findings_ready"],
            "mayGenerateLetters": (not paused) and ef["selections_saved"],
        },
    }


def build_instructor_participant_progress_view(
    user_id: int, enrollment_id: int
) -> Dict[str, Any]:
    """Dual-state shape for instructor detail (includes system + effective)."""
    payload = build_me_program_progress_payload(user_id, enrollment_id)
    return {
        "progressionReadContract": payload["progressionReadContract"],
        "systemState": payload["systemState"],
        "instructorState": payload["instructorState"],
        "effectiveState": payload["effectiveState"],
        "gates": payload["gates"],
        "stepTimestamps": payload["stepTimestamps"],
    }


def participant_forward_paused(user_id: int, enrollment_id: int) -> bool:
    st = refresh_program_progress(user_id, enrollment_id)
    return bool(st["row"].get("instructor_paused"))


def effective_findings_ready(user_id: int, enrollment_id: int) -> bool:
    st = refresh_program_progress(user_id, enrollment_id)
    ef = build_effective_milestone_flags(st["flags"], st["row"])
    return bool(ef.get("findings_ready"))


def effective_upload_done(user_id: int, enrollment_id: int) -> bool:
    st = refresh_program_progress(user_id, enrollment_id)
    ef = build_effective_milestone_flags(st["flags"], st["row"])
    return bool(ef.get("upload"))


def effective_selections_saved(user_id: int, enrollment_id: int) -> bool:
    st = refresh_program_progress(user_id, enrollment_id)
    ef = build_effective_milestone_flags(st["flags"], st["row"])
    return bool(ef.get("selections_saved"))


def apply_instructor_program_override(
    enrollment_id: int,
    participant_user_id: int,
    instructor_user_id: int,
    action: str,
    target_step: Optional[str] = None,
    reason_safe: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    S5B instructor overlay on ``organization_program_progress``.

    * ``pause`` / ``resume`` — row flags only (gating); engine unchanged.
    * ``advance`` — updates overlay **and** completes ``orgprog_*`` steps through the target
      via ``WorkflowEngine`` (``advance_org_program_steps``); engine remains sole write
      authority for step completion.
    * ``reset`` — overlay only; does **not** rewind ``workflow_steps`` (gating may lag
      canonical head).
    """
    act = (action or "").strip().lower()
    if act not in ("pause", "resume", "advance", "reset"):
        return None, "action must be pause, resume, advance, or reset."
    row = ensure_program_progress_row(enrollment_id, participant_user_id)
    if int(row.get("user_id") or 0) != int(participant_user_id):
        return None, "Enrollment user mismatch."

    reason = (reason_safe or "").strip()[:500] or None

    if act == "pause":
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"""
                UPDATE organization_program_progress
                SET instructor_paused = TRUE,
                    instructor_override_at = CURRENT_TIMESTAMP,
                    instructor_override_by_user_id = %s,
                    instructor_override_reason_safe = COALESCE(%s, instructor_override_reason_safe),
                    updated_at = CURRENT_TIMESTAMP
                WHERE organization_program_enrollment_id = %s
                RETURNING {_progress_select_columns()}
                """,
                (instructor_user_id, reason, enrollment_id),
            )
            out = _row_to_dict(cur.fetchone())
            conn.commit()
        return out, None

    if act == "resume":
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"""
                UPDATE organization_program_progress
                SET instructor_paused = FALSE,
                    instructor_override_kind = NULL,
                    instructor_override_step = NULL,
                    instructor_override_at = CURRENT_TIMESTAMP,
                    instructor_override_by_user_id = %s,
                    instructor_override_reason_safe = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE organization_program_enrollment_id = %s
                RETURNING {_progress_select_columns()}
                """,
                (instructor_user_id, reason, enrollment_id),
            )
            out = _row_to_dict(cur.fetchone())
            conn.commit()
        return out, None

    if act in ("advance", "reset"):
        ts = (target_step or "").strip()
        if not ts:
            return None, "targetStep is required for advance and reset."
        if step_index(ts) is None:
            return None, f"targetStep must be one of: {', '.join(PROGRAM_STEPS)}."
        kind = "advance" if act == "advance" else "reset"
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"""
                UPDATE organization_program_progress
                SET instructor_paused = FALSE,
                    instructor_override_kind = %s,
                    instructor_override_step = %s,
                    instructor_override_at = CURRENT_TIMESTAMP,
                    instructor_override_by_user_id = %s,
                    instructor_override_reason_safe = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE organization_program_enrollment_id = %s
                RETURNING {_progress_select_columns()}
                """,
                (kind, ts, instructor_user_id, reason, enrollment_id),
            )
            out = _row_to_dict(cur.fetchone())
            conn.commit()
        if act == "advance":
            org_id = _organization_id_for_enrollment(enrollment_id)
            if org_id is None:
                return None, "Enrollment organization not found."
            step_ids = orgprog_step_ids_through_milestone(ts)
            if step_ids:
                from services.org_program_workflow_service import advance_org_program_steps

                advance_org_program_steps(
                    participant_user_id,
                    org_id,
                    enrollment_id,
                    step_ids,
                    audit_source="instructor_override:advance",
                )
        return out, None

    return None, "Unsupported action."
