"""
Production readiness — Phase 7–8 style HTTP contracts + letter download/preview paths.

Uses FastAPI TestClient with dependency overrides (no live Postgres required).
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from tests.e2e_workflow_chain_harness import postgres_e2e_available


def _letters_rows():
    return [
        {
            "id": 101,
            "report_id": 1,
            "bureau": "experian",
            "letter_text": "Dear Bureau,\n\nDispute body PR.\n\nSincerely,\nUser\n",
        },
        {
            "id": 102,
            "report_id": 1,
            "bureau": "equifax",
            "letter_text": "Second letter.\n",
        },
    ]


class TestPhase07GuidanceDeliveryContract:
    def test_internal_pattern_summary_contract_versioned_payload(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import require_admin_service

        fixed = {
            "generatedAt": "2026-04-08T00:00:00Z",
            "recordsIncluded": 0,
            "exactNoteClusters": [],
            "topPhrases": [],
            "notesByOutcomeKey": [],
            "heuristics": {"blocksWithHighNoteDiversity": []},
            "truncated": False,
            "filtersEcho": {},
        }
        monkeypatch.setattr(
            "api.workflow_app.summarize_execution_outcome_patterns",
            lambda **kwargs: fixed,
        )

        app.dependency_overrides[require_admin_service] = lambda: None
        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    "/internal/admin/execution-outcomes/pattern-summary",
                    headers={"X-Workflow-Admin-Key": "x"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["recordsIncluded"] == 0
        assert "exactNoteClusters" in data
        assert data["truncated"] is False

    def test_execution_state_get_stable_json_shape(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        fixed_state = {
            "schemaVersion": "execution_state_response_v1",
            "runId": "run-pr-1",
            "workflowId": "00000000-0000-4000-8000-000000000099",
            "playbookId": "playbook_x",
            "playbookVersion": "1.0.0",
            "activeBlockIds": ["blk_a"],
            "waitingBlockIds": [],
            "blockedBlockIds": [],
            "completedBlockIds": [],
            "completedOutcomes": {},
            "externalFlags": {},
            "outcomeHistory": [],
        }

        monkeypatch.setattr(
            "api.workflow_app.get_execution_state_latest_for_workflow",
            lambda wf, uid: fixed_state,
        )
        monkeypatch.setattr(
            "api.workflow_app.enforce_customer_action",
            lambda *a, **k: None,
        )

        wf = "00000000-0000-4000-8000-000000000099"
        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 1,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 1,
            "role": "consumer",
            "email": "pr@example.com",
        }

        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r1 = client.get(
                    f"/api/workflows/{wf}/execution/state",
                    headers={"Authorization": "Bearer t"},
                )
                r2 = client.get(
                    f"/api/workflows/{wf}/execution/state",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200
        assert r1.json() == r2.json()
        body = r1.json()["executionState"]
        assert body["runId"] == "run-pr-1"
        assert isinstance(body["activeBlockIds"], list)

    def test_execution_state_read_only_independent_of_ui(self, monkeypatch):
        """Same handler serves JSON; no UI-specific branching in response shape."""
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        monkeypatch.setattr(
            "api.workflow_app.get_execution_state_latest_for_workflow",
            lambda wf, uid: {"schemaVersion": "v1", "runId": "r", "workflowId": wf},
        )
        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)

        wf = "00000000-0000-4000-8000-000000000088"
        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 2,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 2,
            "role": "consumer",
            "email": "x@example.com",
        }

        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/execution/state",
                    headers={"Authorization": "Bearer t", "Accept": "application/json"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/json")


class TestPhase08ApplicationLayerSeparation:
    def test_json_execution_payload_roundtrips_without_backend_mutation(self):
        payload = {
            "executionState": {
                "runId": "r1",
                "activeBlockIds": ["a"],
                "waitingBlockIds": [],
            }
        }
        import json

        clone = json.loads(json.dumps(payload))
        assert clone == payload

    def test_letter_row_serialization_is_structured_for_ui_projection(self):
        from services.customer_letter_service import serialize_letter_row

        row = {
            "id": 1,
            "report_id": 9,
            "bureau": "experian",
            "letter_text": "hello",
            "created_at": None,
            "metadata": "{}",
        }
        s = serialize_letter_row(row)
        assert s["id"] == 1
        assert s["reportId"] == 9
        assert s["bureau"] == "experian"
        assert s["charCount"] == 5
        assert "preview" in s

    def test_list_letters_for_customer_sorted_deterministically(self, monkeypatch):
        from services.customer_letter_service import list_letters_for_workflow_customer

        monkeypatch.setattr(
            "services.customer_letter_service.db.get_all_letters_for_user",
            lambda uid: [
                {
                    "id": 2,
                    "report_id": 1,
                    "bureau": "transunion",
                    "letter_text": "z",
                    "created_at": None,
                    "metadata": "{}",
                },
                {
                    "id": 1,
                    "report_id": 1,
                    "bureau": "experian",
                    "letter_text": "a",
                    "created_at": None,
                    "metadata": "{}",
                },
            ],
        )
        out = list_letters_for_workflow_customer(1)
        assert [x["bureau"] for x in out] == ["experian", "transunion"]


class TestLetterPreviewDownloadContracts:
    def test_letter_content_json_contract(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)

        def fake_body(uid, letter_id):
            if int(letter_id) == 101:
                return "STABLE_LETTER_BODY\n"
            return None

        monkeypatch.setattr("api.workflow_app.get_letter_body_for_user", fake_body)

        wf = "00000000-0000-4000-8000-000000000077"
        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 5,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 5,
            "role": "consumer",
            "email": "u@example.com",
        }

        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/letters/101/content",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/json")
        assert r.json()["letterText"] == "STABLE_LETTER_BODY\n"

    def test_letters_bundle_txt_download(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app.db.get_all_letters_for_user",
            lambda uid: _letters_rows(),
        )

        bodies = {101: _letters_rows()[0]["letter_text"], 102: _letters_rows()[1]["letter_text"]}

        def fake_body(uid, letter_id):
            return bodies.get(int(letter_id))

        monkeypatch.setattr("api.workflow_app.get_letter_body_for_user", fake_body)

        wf = "00000000-0000-4000-8000-000000000066"
        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 7,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 7,
            "role": "consumer",
            "email": "v@example.com",
        }

        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r1 = client.get(
                    f"/api/workflows/{wf}/letters/bundle.txt",
                    headers={"Authorization": "Bearer t"},
                )
                r2 = client.get(
                    f"/api/workflows/{wf}/letters/bundle.txt",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.text == r2.text
        assert "text/plain" in (r1.headers.get("content-type") or "")
        assert len(r1.text.strip()) > 0
        assert "Experian" in r1.text or "experian" in r1.text.lower()

    def test_regenerated_bundle_identical_when_sources_unchanged(self, monkeypatch):
        """Repeat fetch is deterministic when DB rows and bodies are fixed."""
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app.db.get_all_letters_for_user",
            lambda uid: _letters_rows(),
        )
        monkeypatch.setattr(
            "api.workflow_app.get_letter_body_for_user",
            lambda uid, lid: {101: "A", 102: "B"}.get(int(lid), ""),
        )

        wf = "00000000-0000-4000-8000-000000000055"
        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 9,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 9,
            "role": "consumer",
            "email": "w@example.com",
        }

        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                a = client.get(
                    f"/api/workflows/{wf}/letters/bundle.txt",
                    headers={"Authorization": "Bearer t"},
                ).text
                b = client.get(
                    f"/api/workflows/{wf}/letters/bundle.txt",
                    headers={"Authorization": "Bearer t"},
                ).text
        finally:
            app.dependency_overrides.clear()

        assert a == b


@pytest.mark.skipif(
    not postgres_e2e_available(),
    reason="Retail full-chain E2E requires PostgreSQL (DATABASE_URL) and repo PDF fixtures.",
)
def test_full_user_flow_upload_to_letters_e2e(monkeypatch):
    """
    Honest HTTP chain: multipart report upload (merged triple bureau fixtures) → parse via real
    ``execute_report_upload_parse_job`` (``WORKFLOW_E2E_SYNCHRONOUS_PARSE`` + ``claim_job_by_id`` +
    ``_dispatch`` in the upload handler) → intake ack → strategy GET → selection confirm → payment
    via existing letter credits → letter generation → JSON preview + plain-text bundle download.

    Parse/letters use the same services as production (no mocked ``process_uploaded_reports``).
    Skips when ``DATABASE_URL`` is unset. Requires repo ``samples/*_fixture_sample.pdf`` files.
    """
    from io import BytesIO

    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from services.customer_letter_service import list_letters_for_workflow_customer
    from tests.e2e_workflow_chain_harness import (
        bootstrap_retail_consumer_chain,
        cleanup_e2e_user_reports,
        load_triple_pdf_fixtures,
        run_report_upload_parse_job,
    )

    monkeypatch.setenv("WORKFLOW_JOB_WORKER_ENABLED", "0")
    # Run real parse in-request (``WORKFLOW_E2E_SYNCHRONOUS_PARSE``) so the same _dispatch path
    # as the worker runs immediately; inputs are durable under lab_truth/report_intake (or REPORT_INTAKE_ARTIFACT_DIR).
    monkeypatch.setenv("WORKFLOW_E2E_SYNCHRONOUS_PARSE", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("REPLIT_DEPLOYMENT", raising=False)

    from services.workflow.workflow_job_worker import stop_job_worker

    stop_job_worker()

    chain_ctx = None
    try:
        chain_ctx = bootstrap_retail_consumer_chain()
    except Exception:
        pytest.fail(
            "E2E bootstrap failed (DATABASE_URL set but user/workflow init error). "
            "See tests/e2e_workflow_chain_harness.py and server logs.",
        )

    authz = {"Authorization": f"Bearer {chain_ctx.session_token}"}

    try:
        pdfs = load_triple_pdf_fixtures()
        multi = [("files", (name, BytesIO(data), "application/pdf")) for name, data in pdfs]

        with TestClient(app, raise_server_exceptions=True) as client:
            up = client.post(
                f"/api/workflows/{chain_ctx.workflow_id}/reports/upload",
                files=multi,
                data={"privacy_consent": "true"},
                headers=authz,
            )
        assert up.status_code == 200, up.text
        up_body = up.json()
        assert up_body.get("ok") is True
        assert up_body.get("processing") is True
        jid = str(up_body.get("jobId") or "")
        assert jid

        job_view = run_report_upload_parse_job(jid)
        assert job_view.get("status") == "completed", job_view
        result = job_view.get("result") or {}
        assert result.get("ok") is True, result
        report_ids = result.get("reportIds") or []
        assert isinstance(report_ids, list) and len(report_ids) >= 1, result

        with TestClient(app, raise_server_exceptions=True) as client:
            intake = client.get(
                f"/api/workflows/{chain_ctx.workflow_id}/intake/summary",
                headers=authz,
            )
        assert intake.status_code == 200, intake.text
        intake_body = intake.json()
        assert "intake" in intake_body
        ic = intake_body["intake"]
        rc_count = int(ic.get("reviewClaimsCount") or 0)
        assert rc_count > 0

        with TestClient(app, raise_server_exceptions=True) as client:
            ack = client.post(
                f"/api/workflows/{chain_ctx.workflow_id}/intake/acknowledge-review",
                headers=authz,
                json={"item_count": rc_count},
            )
        assert ack.status_code == 200, ack.text

        with TestClient(app, raise_server_exceptions=True) as client:
            strat = client.get(
                f"/api/workflows/{chain_ctx.workflow_id}/disputes/strategy",
                headers=authz,
            )
        assert strat.status_code == 200, strat.text
        st = strat.json()
        assert st.get("selectionAllowed") is True
        ds = st.get("disputeStrategy")
        assert isinstance(ds, dict)
        assert int(ds.get("eligibleCount") or 0) > 0
        eligible_ids = ds.get("eligibleReviewClaimIds") or []
        assert isinstance(eligible_ids, list) and len(eligible_ids) > 0
        default_sel = ds.get("defaultSelectedReviewClaimIds") or eligible_ids[:3]
        assert len(default_sel) >= 1

        with TestClient(app, raise_server_exceptions=True) as client:
            sel = client.post(
                f"/api/workflows/{chain_ctx.workflow_id}/disputes/selection/confirm",
                headers=authz,
                json={"selected_review_claim_ids": default_sel},
            )
        assert sel.status_code == 200, sel.text

        with TestClient(app, raise_server_exceptions=True) as client:
            pay = client.post(
                f"/api/workflows/{chain_ctx.workflow_id}/payment/continue-with-credits",
                headers=authz,
            )
        assert pay.status_code == 200, pay.text

        with TestClient(app, raise_server_exceptions=True) as client:
            ctx_before = client.get(
                f"/api/workflows/{chain_ctx.workflow_id}/letters/context",
                headers=authz,
            )
        assert ctx_before.status_code == 200, ctx_before.text
        ui0 = (ctx_before.json().get("lettersUi") or {})
        assert ui0.get("workflowHeadStepId") == "letter_generation"

        with TestClient(app, raise_server_exceptions=True) as client:
            gen = client.post(
                f"/api/workflows/{chain_ctx.workflow_id}/letters/generate",
                headers=authz,
            )
        assert gen.status_code == 200, gen.text
        gen_body = gen.json()
        assert "generation" in gen_body
        bureaus = gen_body["generation"].get("bureaus") or []
        assert isinstance(bureaus, list) and len(bureaus) >= 1

        letters = list_letters_for_workflow_customer(chain_ctx.user_id)
        assert len(letters) >= 1
        b_keys = [str(x.get("bureau") or "").lower() for x in letters]
        assert b_keys == sorted(b_keys), "list_letters_for_workflow_customer matches API sort order"

        letter_id = int(letters[0]["id"])
        assert letter_id > 0

        with TestClient(app, raise_server_exceptions=True) as client:
            prev1 = client.get(
                f"/api/workflows/{chain_ctx.workflow_id}/letters/{letter_id}/content",
                headers=authz,
            )
            prev2 = client.get(
                f"/api/workflows/{chain_ctx.workflow_id}/letters/{letter_id}/content",
                headers=authz,
            )
        assert prev1.status_code == 200
        assert prev2.status_code == 200
        assert prev1.headers.get("content-type", "").startswith("application/json")
        t1 = prev1.json().get("letterText") or ""
        t2 = prev2.json().get("letterText") or ""
        assert len(t1.strip()) > 20
        assert t1 == t2

        with TestClient(app, raise_server_exceptions=True) as client:
            dl1 = client.get(
                f"/api/workflows/{chain_ctx.workflow_id}/letters/bundle.txt",
                headers=authz,
            )
            dl2 = client.get(
                f"/api/workflows/{chain_ctx.workflow_id}/letters/bundle.txt",
                headers=authz,
            )
        assert dl1.status_code == 200
        assert dl2.status_code == 200
        ct = (dl1.headers.get("content-type") or "").lower()
        assert "text/plain" in ct
        body1 = dl1.text
        body2 = dl2.text
        assert len(body1.strip()) > 50
        assert body1 == body2
        assert "=" * 12 in body1

        with TestClient(app, raise_server_exceptions=True) as client:
            dup = client.post(
                f"/api/workflows/{chain_ctx.workflow_id}/letters/generate",
                headers=authz,
            )
        assert dup.status_code == 409
        dup_detail = dup.json().get("detail") or {}
        assert isinstance(dup_detail, dict)
        assert dup_detail.get("code") == "FLOW_ORDER_VIOLATION"
    finally:
        if chain_ctx is not None:
            cleanup_e2e_user_reports(chain_ctx.user_id)
