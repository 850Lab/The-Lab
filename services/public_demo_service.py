"""
Server-side public demo: one-shot fixture run through the **same progression engine** as
customers — ``WorkflowEngine`` + ``workflow_sessions`` / ``workflow_steps`` (not a parallel
demo state machine). The HTTP response shape is tailored for the React demo UI; step
advances use ``services.workflow.hooks`` like production.

Runs as a **dedicated system user** in the database (visitors never log in as that user).
If ``PUBLIC_DEMO_USER_ID`` is unset, the API **creates** ``INTERNAL_PUBLIC_DEMO_EMAIL`` on
first use and reuses it. Override with ``PUBLIC_DEMO_USER_ID`` when you want a specific row.

See env ``PUBLIC_DEMO_*`` in ``.env.example``. Operators: ``python scripts/ensure_public_demo_test_account.py``.
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg2

import auth as auth_module
import database as db
from services.public_demo_fixtures_manifest import demo_scenarios, REPO_ROOT as _REPO_ROOT
from services.public_demo_visitor_placeholders import apply_public_demo_visitor_mask
from dispute_strategy import build_deterministic_strategy
from services.customer_dispute_strategy import (
    dispute_selection_context_from_meta,
    estimate_unique_bureaus_for_claims,
    filter_eligible_dispute_items,
    load_compressed_review_claims_for_user,
    parse_workflow_metadata_value,
)
from services.customer_intake_summary import build_customer_intake_summary
from services.customer_letter_service import (
    build_credit_command_plan_for_workflow,
    get_letter_body_for_user,
    list_letters_for_workflow_customer,
    run_letter_generation,
)
from services.workflow_payment_service import (
    complete_payment_with_existing_letter_entitlements,
    needed_letters_from_workflow_session,
)
from services.workflow import hooks as workflow_hooks
from services.workflow.engine import WorkflowEngine
from services.workflow.repository import fetch_session

_log = logging.getLogger(__name__)

_PUBLIC_DEMO_PER_CLAIM_SUMMARY_MAX = 400


def _public_demo_per_claim_summary(raw: Optional[str]) -> str:
    s = (raw or "").strip().replace("\n", " ")
    if not s:
        return ""
    if len(s) <= _PUBLIC_DEMO_PER_CLAIM_SUMMARY_MAX:
        return s
    return s[: _PUBLIC_DEMO_PER_CLAIM_SUMMARY_MAX - 1].rstrip() + "…"

# Reserved address (``.invalid`` TLD); not for human signup. Used when PUBLIC_DEMO_USER_ID is unset.
INTERNAL_PUBLIC_DEMO_EMAIL = "850lab.public.demo@internal.invalid"
# Shown in admin/UI for this row — clearly not a real consumer.
SYNTHETIC_DEMO_DISPLAY_NAME = "Synthetic demo consumer (fictional)"

# Landing demo UI expects three bureau letters; each fixture PDF is one bureau, so letter
# generation often produces a single row. We pad missing bureaus with negative ids (no DB row);
# visitor masking fills preview/body with synthetic per-bureau text.
_TRIPLE_BUREAU_SLOTS: Tuple[Tuple[str, str, str], ...] = (
    ("equifax", "equifax", "Equifax"),
    ("transunion", "transunion", "TransUnion"),
    ("experian", "experian", "Experian"),
)


def _demo_letter_bureau_key(letter: Dict[str, Any]) -> str:
    blob = f"{letter.get('bureau') or ''} {letter.get('bureauDisplay') or ''}".lower().replace(
        " ", ""
    )
    if "equifax" in blob:
        return "equifax"
    if "experian" in blob:
        return "experian"
    if "transunion" in blob:
        return "transunion"
    return ""


def _pad_public_demo_letters_to_three_bureaus(letters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    present: Set[str] = set()
    for L in letters:
        k = _demo_letter_bureau_key(L)
        if k:
            present.add(k)
    out = list(letters)
    sid = -1
    for key_lower, bureau_field, display in _TRIPLE_BUREAU_SLOTS:
        if key_lower in present:
            continue
        out.append(
            {
                "id": sid,
                "bureau": bureau_field,
                "bureauDisplay": display,
                "preview": "",
                "charCount": 0,
                "body": "",
            }
        )
        sid -= 1
        present.add(key_lower)
    order = {"equifax": 0, "transunion": 1, "experian": 2}
    out.sort(
        key=lambda Lx: (
            order.get(_demo_letter_bureau_key(Lx), 9),
            str(Lx.get("bureauDisplay") or ""),
        )
    )
    return out


def _report_ids_from_upload_result(result: Dict[str, Any]) -> List[int]:
    """Persisted ``reports.id`` values produced by this upload pipeline run only."""
    out: List[int] = []
    for v in (result.get("uploaded_reports") or {}).values():
        if not isinstance(v, dict):
            continue
        rid = v.get("report_id")
        if rid is None:
            continue
        try:
            out.append(int(rid))
        except (TypeError, ValueError):
            pass
    return out


def _public_demo_email_permitted(email: Optional[str]) -> bool:
    """
    Refuse to run the visitor-facing demo on a normal customer row unless the operator
    explicitly opts in (see ``PUBLIC_DEMO_ALLOW_NON_SYNTHETIC_USER`` in ``.env.example``).
    """
    if (os.environ.get("PUBLIC_DEMO_ALLOW_NON_SYNTHETIC_USER") or "").strip() == "1":
        return True
    e = (email or "").strip().lower()
    if e == INTERNAL_PUBLIC_DEMO_EMAIL.strip().lower():
        return True
    if e.endswith("@internal.invalid"):
        return True
    return False


def _normalized_public_demo_user_id_raw() -> str:
    """Strip whitespace and optional surrounding quotes from env (common in .env files)."""
    raw = (os.environ.get("PUBLIC_DEMO_USER_ID") or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1].strip()
    return raw


def _record_demo_fixture_completed(
    workflow_id: str,
    scenario_id: str,
    *,
    partial: bool,
    reason: Optional[str] = None,
) -> None:
    from services.workflow.workflow_event_service import record_system_event

    meta: Dict[str, Any] = {"scenarioId": scenario_id, "partial": partial}
    if reason:
        meta["reason"] = reason
    record_system_event(
        workflow_id,
        "demo.fixture_run_completed",
        actor="demo",
        source="demo",
        metadata=meta,
    )

def is_production_like_public_demo_deploy() -> bool:
    """
    When True, public demo must be explicitly enabled (``PUBLIC_DEMO_ENABLED=1``).

    Local / preview Repls often omit REPLIT_DEPLOYMENT; `/api/public/demo/*` can run with
    an auto-provisioned demo user (no ``PUBLIC_DEMO_USER_ID`` required).
    """
    if (os.environ.get("REPLIT_DEPLOYMENT") or "").strip() == "1":
        return True
    env = (os.environ.get("ENVIRONMENT") or "").strip().lower()
    if env in ("production", "prod"):
        return True
    return False


def public_demo_config_error() -> Optional[str]:
    if is_production_like_public_demo_deploy() and (os.environ.get("PUBLIC_DEMO_ENABLED") or "").strip() != "1":
        return "Public demo is not enabled (set PUBLIC_DEMO_ENABLED=1 on production deploys)."
    raw = _normalized_public_demo_user_id_raw()
    if raw and (not raw.isdigit() or int(raw) < 1):
        return (
            "PUBLIC_DEMO_USER_ID must be a positive integer users.id when set "
            "(or remove it to use the auto-provisioned demo account)."
        )
    return None


def _get_or_create_internal_public_demo_user_id() -> Tuple[Optional[int], Optional[str]]:
    """
    Ensure the synthetic demo row exists. Returns (user_id, error_message).
    """
    email = INTERNAL_PUBLIC_DEMO_EMAIL.strip().lower()
    try:
        with db.get_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                "SELECT id FROM users WHERE LOWER(TRIM(email)) = %s",
                (email,),
            )
            row = cur.fetchone()
            if row:
                return int(row["id"]), None
            pw_hash = auth_module.hash_password(secrets.token_urlsafe(48))
            cur.execute(
                """
                INSERT INTO users (email, password_hash, display_name, role, email_verified)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    email,
                    pw_hash,
                    SYNTHETIC_DEMO_DISPLAY_NAME,
                    "consumer",
                    True,
                ),
            )
            ins = cur.fetchone()
            conn.commit()
            uid = int(ins["id"])
    except psycopg2.errors.UniqueViolation:
        with db.get_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                "SELECT id FROM users WHERE LOWER(TRIM(email)) = %s",
                (email,),
            )
            row = cur.fetchone()
            if row:
                return int(row["id"]), None
        return None, "Could not resolve internal public demo user after unique conflict."
    except Exception:
        _log.exception("internal public demo user provisioning failed")
        return (
            None,
            "Could not create the internal public demo user. Check DATABASE_URL and that auth tables exist.",
        )

    try:
        auth_module.add_entitlements(
            uid,
            ai_rounds=10,
            letters=40,
            mailings=15,
            source="public_demo_auto_user",
            note="Auto-provisioned public demo account",
        )
    except Exception:
        _log.warning(
            "public demo auto user entitlements failed uid=%s",
            uid,
            exc_info=True,
        )

    return uid, None


def _normalize_synthetic_demo_user_profile(user_id: int) -> None:
    """Set display name so the row is obviously fictional (fixes legacy auto-created rows)."""
    email = INTERNAL_PUBLIC_DEMO_EMAIL.strip().lower()
    try:
        with db.get_db() as (conn, cur):
            cur.execute(
                """
                UPDATE users
                SET display_name = %s
                WHERE id = %s AND LOWER(TRIM(email)) = %s
                """,
                (SYNTHETIC_DEMO_DISPLAY_NAME, int(user_id), email),
            )
            conn.commit()
    except Exception:
        _log.warning(
            "could not normalize synthetic demo display_name uid=%s",
            user_id,
            exc_info=True,
        )


def ensure_public_demo_test_account(
    *,
    top_up_entitlements: bool = False,
) -> Tuple[int, str]:
    """
    Create (if missing) the reserved synthetic demo user, normalize profile, optionally
    add more starter credits. For operators / CI — does **not** require ``PUBLIC_DEMO_ENABLED``.

    Returns ``(users.id, email)``. Password is random and not retrievable; this account is
    not for human login — only for the visitor fixture demo pipeline.
    """
    uid, msg = _get_or_create_internal_public_demo_user_id()
    if uid is None:
        raise RuntimeError(msg or "Could not ensure synthetic public demo user")
    _normalize_synthetic_demo_user_profile(uid)
    if top_up_entitlements:
        auth_module.add_entitlements(
            uid,
            ai_rounds=10,
            letters=40,
            mailings=15,
            source="public_demo_ensure_script",
            note="scripts/ensure_public_demo_test_account.py --top-up",
        )
    return uid, INTERNAL_PUBLIC_DEMO_EMAIL.strip()


def demo_user_id() -> int:
    err = public_demo_config_error()
    if err:
        raise RuntimeError(err)
    raw = _normalized_public_demo_user_id_raw()
    if raw.isdigit() and int(raw) >= 1:
        uid = int(raw)
        user = _user_row(uid)
        if not user:
            raise RuntimeError(
                f"PUBLIC_DEMO_USER_ID={uid} has no matching users row."
            )
        return uid
    uid, msg = _get_or_create_internal_public_demo_user_id()
    if uid is None:
        raise RuntimeError(msg or "Could not resolve public demo user.")
    return uid


def list_demo_scenarios_public() -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for sid, meta in demo_scenarios().items():
        rel = meta["file"]
        path = _REPO_ROOT / rel
        if not path.is_file():
            continue
        out.append(
            {
                "scenarioId": sid,
                "title": meta["title"],
                "description": meta["description"],
                "category": meta.get("category", "general"),
                "categoryLabel": meta.get("category_label", ""),
            }
        )
    return out


def _scenario_path(scenario_id: str) -> Tuple[Optional[Path], Optional[str]]:
    meta = demo_scenarios().get((scenario_id or "").strip())
    if not meta:
        return None, "Unknown scenario."
    path = _REPO_ROOT / meta["file"]
    if not path.is_file():
        return None, f"Fixture file missing: {meta['file']}"
    return path, None


def _pdf_pairs_for_public_demo(scenario_id: str) -> Tuple[List[Tuple[str, bytes]], Optional[str]]:
    """
    One upload batch = TU + Experian + Equifax fixtures (same multi-file path as member uploads).
    ``fixture_bundle`` in scenario config lists relative paths; falls back to primary ``file`` only.
    """
    sid = (scenario_id or "").strip()
    meta = demo_scenarios().get(sid)
    if not meta:
        return [], "Unknown scenario."
    bundle = meta.get("fixture_bundle")
    rels: List[str] = []
    if isinstance(bundle, list):
        rels = [str(x).strip() for x in bundle if str(x).strip()]
    if len(rels) < 3:
        primary = str(meta.get("file") or "").strip()
        if not primary:
            return [], "Scenario has no primary fixture file."
        rels = [
            primary,
            "samples/experian_fixture_sample.pdf",
            "samples/equifax_fixture_sample.pdf",
        ]
    pairs: List[Tuple[str, bytes]] = []
    for rel in rels[:3]:
        p = _REPO_ROOT / rel
        if not p.is_file():
            return [], f"Fixture file missing: {rel}"
        pairs.append((p.name, p.read_bytes()))
    return pairs, None


def _user_row(user_id: int) -> Optional[Dict[str, Any]]:
    with db.get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            "SELECT id, email, role FROM users WHERE id = %s",
            (user_id,),
        )
        return cur.fetchone()


def run_public_fixture_demo(scenario_id: str) -> Dict[str, Any]:
    """
    Create a new workflow for the demo user, ingest fixture PDFs (default: all three bureau
    samples in one ``process_uploaded_reports`` batch, same as a triple upload in-app),
    auto-select disputes, waive payment, generate letters, and return JSON for the React demo.
    """
    uid = demo_user_id()
    pdf_pairs, pair_err = _pdf_pairs_for_public_demo(scenario_id)
    if not pdf_pairs:
        path, err = _scenario_path(scenario_id)
        if err:
            return {"ok": False, "error": pair_err or err}
        pdf_pairs = [(path.name, path.read_bytes())]

    user = _user_row(uid)
    if not user:
        return {"ok": False, "error": "Demo user id does not exist in the database."}

    if not _public_demo_email_permitted(user.get("email")):
        _log.error(
            "public demo refused: users.id=%s is not an approved synthetic demo account (email=%r)",
            uid,
            user.get("email"),
        )
        return {
            "ok": False,
            "error": (
                "Public demo user is not a dedicated synthetic account. Unset PUBLIC_DEMO_USER_ID "
                "to use the auto-created demo account, or set PUBLIC_DEMO_ALLOW_NON_SYNTHETIC_USER=1 "
                "only if you accept serious privacy and compliance risk."
            ),
        }

    engine = WorkflowEngine()
    init_env = engine.init_workflow(
        user_id=uid,
        metadata={
            "public_demo": True,
            "public_demo_scenario": scenario_id,
        },
    )
    ws = init_env.get("workflowState") or {}
    workflow_id = (ws.get("workflowId") or "").strip()
    if not workflow_id:
        return {"ok": False, "error": "Could not create demo workflow."}

    try:
        from services.report_pipeline import process_uploaded_reports

        result = process_uploaded_reports(
            pdf_pairs,
            {
                "user_id": uid,
                "workflow_id": workflow_id,
                "mutation_channel": "public_demo",
            },
        )
    except Exception:
        _log.exception("public demo pipeline failed wf=%s", workflow_id)
        return {"ok": False, "error": "Report processing failed for this fixture."}

    processed = int(result.get("reports_processed") or 0)
    skips = result.get("file_skips") or []
    report_ids = _report_ids_from_upload_result(result)
    if processed < 1 or skips:
        return {
            "ok": False,
            "error": "Fixture did not produce a parsed report.",
            "workflowId": workflow_id,
            "fileSkips": skips,
        }

    if not report_ids:
        _log.error(
            "public demo: reports_processed=%s but no report_id in uploaded_reports wf=%s",
            processed,
            workflow_id,
        )
        return {
            "ok": False,
            "error": "Demo pipeline did not return report identifiers.",
            "workflowId": workflow_id,
        }

    intake = build_customer_intake_summary(uid, only_report_ids=report_ids)
    item_count = int(intake.get("reviewClaimsCount") or 0)
    workflow_hooks.notify_review_claims_completed(
        uid,
        workflow_id=workflow_id,
        item_count=item_count,
        audit_source="public_demo",
    )

    claims = load_compressed_review_claims_for_user(uid, only_report_ids=report_ids)
    sess = fetch_session(workflow_id)
    meta = parse_workflow_metadata_value(sess.get("metadata") if sess else {})
    rnd, cumulative, outcomes = dispute_selection_context_from_meta(meta)
    eligible = filter_eligible_dispute_items(
        claims,
        round_number=rnd,
        cumulative_disputed_ids=cumulative,
        claim_outcomes=outcomes,
    )
    if not eligible:
        _record_demo_fixture_completed(
            workflow_id,
            scenario_id,
            partial=True,
            reason="no_eligible_items",
        )
        out_partial = {
            "ok": True,
            "partial": True,
            "workflowId": workflow_id,
            "scenarioId": scenario_id,
            "intake": _trim_intake(intake),
            "message": "No eligible dispute items were found after parsing (fixture may be clean).",
            "creditCommandPlan": None,
            "letters": [],
            "strategy": None,
        }
        apply_visitor_placeholders(out_partial, scenario_id)
        return out_partial

    round_size = min(10, max(1, len(eligible)))
    det = build_deterministic_strategy(
        eligible, round_size=round_size, excluded_ids=[]
    )
    ids = [sc.review_claim.review_claim_id for sc in det.selected_claims]
    eligible_by_id = {rc.review_claim_id: rc for rc in eligible}
    bureaus = estimate_unique_bureaus_for_claims(eligible_by_id, ids)

    ok_sel = workflow_hooks.complete_select_disputes_step(
        uid,
        workflow_id,
        selected_count=len(ids),
        bureaus=bureaus,
        selected_review_claim_ids=ids,
        audit_source="public_demo",
    )
    if not ok_sel:
        return {
            "ok": False,
            "error": "Could not advance dispute selection for demo workflow.",
            "workflowId": workflow_id,
        }

    sess2 = fetch_session(workflow_id)
    if not sess2:
        return {"ok": False, "error": "Lost workflow session after selection."}

    waived = workflow_hooks.notify_payment_waived(
        uid,
        workflow_id=workflow_id,
        actor_source="public_demo",
        reason_safe="Guided public demo — payment step waived for showcase account.",
    )
    if not waived:
        needed = needed_letters_from_workflow_session(sess2)
        waived = complete_payment_with_existing_letter_entitlements(
            workflow_id, uid, needed
        )
    if not waived:
        _log.warning("public demo could not complete payment step wf=%s", workflow_id)

    sess2 = fetch_session(workflow_id) or sess2

    _, gen_err = run_letter_generation(
        uid,
        workflow_id,
        session_row=sess2,
        is_admin=True,
        only_report_ids=report_ids,
    )
    if gen_err:
        _log.warning("public demo letter generation: %s", gen_err)

    sess3 = fetch_session(workflow_id) or sess2
    plan, _plan_err = build_credit_command_plan_for_workflow(
        uid,
        workflow_id,
        session_row=sess3,
        is_admin=True,
        record_observability_event=True,
        only_report_ids=report_ids,
    )

    letter_rows = list_letters_for_workflow_customer(uid, only_report_ids=report_ids)
    letters_out: List[Dict[str, Any]] = []
    for row in letter_rows:
        lid = row.get("id")
        body = ""
        if lid is not None and int(lid) > 0:
            body = get_letter_body_for_user(uid, int(lid)) or ""
        letters_out.append(
            {
                "id": lid,
                "bureau": row.get("bureau"),
                "bureauDisplay": row.get("bureauDisplay"),
                "preview": row.get("preview"),
                "charCount": row.get("charCount"),
                "body": body,
            }
        )

    letters_out = _pad_public_demo_letters_to_three_bureaus(letters_out)

    strategy_payload = {
        "source": det.source,
        "rationale": det.rationale,
        "roundSummary": det.round_summary,
        "selectedReviewClaimIds": ids,
        "selectedCount": len(ids),
        "perClaim": [
            {
                "reviewClaimId": sc.review_claim.review_claim_id,
                "rank": sc.rank,
                "impactScore": round(sc.impact_score, 2),
                "reviewType": sc.review_claim.review_type.value,
                "summary": _public_demo_per_claim_summary(sc.review_claim.summary),
            }
            for sc in det.selected_claims
        ],
    }

    _record_demo_fixture_completed(
        workflow_id,
        scenario_id,
        partial=bool(gen_err) or not waived,
    )

    out_ok: Dict[str, Any] = {
        "ok": True,
        "partial": bool(gen_err) or not waived,
        "workflowId": workflow_id,
        "scenarioId": scenario_id,
        "scenarioTitle": demo_scenarios().get(scenario_id, {}).get("title", scenario_id),
        "reportsProcessed": processed,
        "intake": _trim_intake(intake),
        "strategy": strategy_payload,
        "letters": letters_out,
        "creditCommandPlan": plan,
        "letterGenerationNote": gen_err,
        "paymentWaived": waived,
        "demoUserEmailMasked": _mask_email(user.get("email")),
    }
    apply_public_demo_visitor_mask(out_ok, scenario_id)
    return out_ok


def _mask_email(email: Optional[str]) -> str:
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        return f"•••@{domain}"
    return f"{local[0]}•••{local[-1]}@{domain}"


def _trim_intake(intake: Dict[str, Any], max_claims: int = 40) -> Dict[str, Any]:
    """Avoid multi-megabyte JSON in the demo API response."""
    data = dict(intake)
    rc = data.get("reviewClaims")
    if isinstance(rc, list) and len(rc) > max_claims:
        data["reviewClaims"] = rc[:max_claims]
        data["reviewClaimsTruncated"] = True
        data["reviewClaimsOmitted"] = len(rc) - max_claims
    else:
        data["reviewClaimsTruncated"] = False
    return data
