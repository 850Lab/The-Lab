# 850 Lab — Workflow API (backend authority)

The workflow engine owns **progression truth**. Clients (Streamlit, React) must not advance steps except through authenticated user actions that the engine allows, or through **trusted internal** calls.

## Run

```bash
pip install fastapi uvicorn
# From repo root, DATABASE_URL / DB config as for main app
uvicorn api.workflow_app:app --host 0.0.0.0 --port 8000
```

## Authentication

| Caller | Mechanism |
|--------|-----------|
| User routes | `Authorization: Bearer <session_token>` (`auth.validate_session`) |
| Internal workers | `X-Workflow-Internal-Key` or `Authorization: Bearer <WORKFLOW_INTERNAL_API_SECRET>` |
| Admin / operators | `X-Workflow-Admin-Key` or `Authorization: Bearer <WORKFLOW_ADMIN_API_SECRET>` |

**All** `/internal/admin/...` routes require **`WORKFLOW_ADMIN_API_SECRET`** (not the internal worker secret).

### Customer auth (standalone React; same `sessions` rows as Streamlit)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/login` | JSON `{ "email", "password" }` → `auth.authenticate_user` + `auth.create_session`. Returns `{ "token", "user": { id, email, displayName, role, tier, emailVerified } }`. |
| POST | `/api/auth/signup` | JSON `{ "email", "password", "display_name" }` (password rules match Streamlit). `auth.create_user` + `create_session`. Returns `{ "token", "user" }`. New accounts have `emailVerified: false`. |
| POST | `/api/auth/logout` | `Authorization: Bearer <token>`. `auth.delete_session`. Returns `{ "ok": true }`. |
| GET | `/api/auth/me` | Bearer required. Returns `{ "user": { … } }` from session + `users` row. |
| POST | `/api/auth/verify-email` | Bearer + JSON `{ "code" }`. `auth.verify_email_code`. |
| POST | `/api/auth/resend-verification` | Bearer. Generates/sends code via `resend_client.send_verification_email` (may return 503 if email unavailable). |

## User-facing endpoints (session required)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/workflows/init` | Create session + seed steps (body: optional `workflow_type`, `metadata`) |
| GET | `/api/workflows/active` | Latest **active** or **failed** workflow id for the signed-in user (`{ "workflowId": string \| null }`); used by the React shell to resume |
| GET | `/api/workflows/{id}/state` | Authoritative state + next actions |
| GET | `/api/workflows/{id}/resume` | Resume-oriented copy |
| GET | `/api/workflows/{id}/integrity-hints` | Deterministic drift flags + `nextRequiredAction` (`upload` \| `pay` \| `generate` \| `proof` \| `mail` \| `track`) from DB steps/session, entitlements, proof uploads, Lob mail gate, and `entitlement_transactions` vs `lob_sends`. See `services.workflow.integrity_hints_service.build_integrity_hints`. React recovery banners consume this; clients must not infer these flags locally. |
| GET | `/api/workflows/{id}/home-summary` | Lifecycle, reminders, recovery hints |
| GET | `/api/workflows/{id}/responses/metrics` | `{ "workflow", "metrics", "guidance" }` — same aggregates as above plus deterministic `guidance`: `{ primaryState, title, message, actionLabel?, actionTarget? }` from metrics only. Precedence (first match): `no_responses_yet` if `totalResponses == 0`; else `escalation_available` if `escalationRecommendedCount >= 1`; else `classification_issues_present` if `classifiedFailureCount >= 1`; else `pending_review` if `unclassifiedOrPendingCount > 0`; else `monitoring_only`. `actionTarget` only when a real customer route applies (e.g. `/escalation`). No raw response text. |
| GET | `/api/workflows/{id}/responses` | `{ "workflow", "responses": [...], "count" }` — recent `workflow_response_intake` rows for the owner (classification, reasoning, escalation JSON) via `services.customer_response_service`. Emits workflow audit `response_list_fetched` (or `response_list_fetch_failed` on DB error). |
| POST | `/api/workflows/{id}/responses/intake` | JSON `ResponseIntakeBody` (`source_type`, `response_channel`, `parsed_summary`, optional `storage_ref`, links). Runs `intake_bureau_response` (classify + `recommend_escalation` + metadata merge). Returns `{ ok, responseId, classification?, escalationRecommendation?, warning?, workflow }`. Emits audit: `response_intake_stored`, then `response_classification_succeeded` or `response_classification_failed`, and `response_escalation_generated` when applicable. |
| POST | `/api/workflows/{id}/events/customer-ux` | JSON `{ "event_name", "step_id" (default `track`), "status", "metadata" }`. Whitelisted UX events: response intake (`response_intake_page_viewed`, `response_history_viewed`, `response_intake_submit_attempted`, `response_list_fetch_failed`); report acquisition (`report_acquisition_page_viewed`, `idiq_option_selected`, `free_report_option_selected`, `upload_existing_report_selected`, `idiq_bridge_viewed`, `idiq_redirect_clicked`). Use `step_id: upload` for acquisition events. Logged via `services.workflow.response_flow_events` → `log_workflow_event` (`source: frontend`). |
| POST | `/api/workflows/{id}/steps/{stepId}/start` | User starts current step |
| POST | `/api/workflows/{id}/reports/upload` | Multipart: `file` (PDF) + form `privacy_consent` (`true` / `1` / `yes` / `on`). Runs `services.report_pipeline.process_uploaded_reports` (same as Streamlit); response includes refreshed `workflow` envelope from `resume` |
| GET | `/api/workflows/{id}/intake/summary` | `{ "workflow": <resume envelope>, "intake": <parsed reports + compressed review claims> }` via `services.customer_intake_summary.build_customer_intake_summary` (same `extract_claims` / `compress_claims` as the report pipeline) |
| POST | `/api/workflows/{id}/intake/acknowledge-review` | JSON body optional `{ "item_count": number }`. Completes step `review_claims` through `services.workflow.hooks.notify_review_claims_completed` (same hook as Streamlit). Returns `{ "workflow": <resume envelope> }` |
| GET | `/api/workflows/{id}/disputes/strategy` | `{ "workflow", "selectionAllowed", "selectionBlockedReason", "disputeStrategy" }` — eligible items grouped by review type, deterministic suggestion, entitlement hints (`services.customer_dispute_strategy.build_dispute_strategy_payload`) |
| PUT | `/api/workflows/{id}/disputes/selection` | JSON `{ "draft_selected_review_claim_ids": string[] }`. Persists draft under `workflow_sessions.metadata.dispute_selection` (does not advance the engine). Returns `{ "workflow" }` |
| POST | `/api/workflows/{id}/disputes/selection/confirm` | JSON `{ "selected_review_claim_ids": string[] }` (non-empty, subset of eligible). Enforces free-plan per-bureau caps when applicable; completes `select_disputes` via `services.workflow.hooks.complete_select_disputes_step` (same mail metadata + engine transition as Streamlit). Returns `{ "workflow" }` |
| GET | `/api/workflows/{id}/payment/context` | `{ "workflow", "payment": { needed letters, recommended pack, entitlements, step flags, Stripe/return-URL readiness } }` via `services.workflow_payment_service.build_payment_context` |
| POST | `/api/workflows/{id}/payment/checkout` | JSON `{ "product_id": string }` (pack or à-la-carte id from `auth.PACKS` / `auth.ALA_CARTE`). Requires current step `payment`. Uses `stripe_client.create_checkout_session` with this `workflow_id` in metadata. **Requires** env `WORKFLOW_CUSTOMER_APP_ORIGIN` or `PUBLIC_APP_ORIGIN` (customer app base URL, no trailing slash) for Stripe success/cancel URLs. Returns `{ "checkoutUrl", "stripeCheckoutSessionId", "workflow" }` |
| POST | `/api/workflows/{id}/payment/reconcile` | JSON `{ "stripe_checkout_session_id": string }`. Verifies session, credits entitlements once per session, then **retries** advancing the `payment` workflow step until success or exhaustion. If credits already exist for the session, **still** attempts step completion (fixes prior partial applies). Returns `reconcile.paymentStepCompleted` (boolean). Idempotent. |
| POST | `/api/workflows/{id}/payment/continue-with-credits` | No body. Completes step `payment` via `WorkflowEngine.service_complete_step` when `auth.has_entitlement` covers `neededLetters` from workflow mail metadata (no Stripe). Returns `{ "workflow" }` |
| GET | `/api/workflows/{id}/letters/context` | `{ "workflow", "letters": [...], "lettersUi": { head step, phase, letter_generation row status, onLetterGenerationStep, selectedReviewClaimCount } }` — DB letter rows (deduped per report+bureau) via `services.customer_letter_service` |
| POST | `/api/workflows/{id}/letters/generate` | No body. Requires current step `letter_generation`. Runs `process_dispute_pipeline` with context rebuilt from reports + `metadata.dispute_selection` (same as Streamlit). On success completes the step via `complete_letter_generation_step`. Returns `{ "workflow", "generation": { bureaus, billing, readinessSummary } }` |
| GET | `/api/workflows/{id}/letters/{letter_id}/content` | `{ "letterText": string }` — full body for the signed-in owner |
| GET | `/api/workflows/{id}/letters/bundle.txt` | `text/plain` bundle of all letters for the user (deduped per report+bureau) |
| GET | `/api/workflows/{id}/proof/context` | `{ "workflow", "proof": { hasGovernmentId, hasAddressProof, hasSignature, governmentId, addressProof summaries, step flags, onProofAttachmentStep, proofStepCompleted, … } }` via `services.customer_proof_service` + `database.has_proof_docs` / `get_proof_docs_for_user` / `get_user_signature` |
| POST | `/api/workflows/{id}/proof/upload` | Multipart: form `doc_type` (`government_id` or `address_proof`) + `file`. Max 5 MB. Runs `doc_validator.validate_proof_document`; saves with `database.save_proof_upload` (passes `workflow_id` into `maybe_notify_proof_attachment_completed`). Returns `{ "workflow", "proof" }` |
| POST | `/api/workflows/{id}/proof/signature` | Multipart: `file` (PNG). Max 2 MB. `database.save_user_signature` (same hook). Returns `{ "workflow", "proof" }` |
| GET | `/api/workflows/{id}/mail/context` | `{ "workflow", "mail": { …, `mailStatus` (authoritative title/message/`primaryState`, pre-send checklist booleans, `perBureau` truth rows with `state` pending/processing/sending_failed/sent_test/sent_live/tracking_available, Lob id, test flag), … } }` via `services.customer_mail_service.build_mail_context_payload` |
| POST | `/api/workflows/{id}/mail/send-bureau` | JSON `{ "bureau", "from_address": { … }, "return_receipt": bool }`. Mailing credit is debited **after** Lob accepts the send. If `REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND=1` and Lob uses a test key, non-admin sends are blocked. Returns `{ "workflow", "lob": { …, "isTest" }, "mail": … }`. |
| GET | `/api/workflows/{id}/tracking/context` | `{ "workflow": <resume envelope>, "tracking": { …, `trackingStatus` (aligned title/message with mail step), bureau rows with `isTestSend` / `lobId`, … } }` — post-send truth from `lob_sends` (latest per bureau/report), mail-gate counts, workflow step flags (`track` / `mail`), 30-day timeline offset from first mailed send, and compact `build_home_summary` hints (`services.customer_tracking_service.build_tracking_context_payload`). Does not call Lob live APIs. |

**There is no public HTTP `complete` or `fail` for steps.** Trusted backends use internal routes below.

## Internal worker endpoints (`WORKFLOW_INTERNAL_API_SECRET`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/internal/workflows/{id}/steps/{stepId}/service-complete` | Trusted completion |
| POST | `/internal/workflows/{id}/steps/{stepId}/service-fail` | Trusted failure |
| POST | `/internal/workflows/{id}/steps/{stepId}/async-state` | Async job state |
| POST | `/internal/reminders/...` | Reminder candidates, queue, **delivery batch**, deliver |

## Admin endpoints (`WORKFLOW_ADMIN_API_SECRET`)

Includes response overrides, reminder skip, reopen failed step, payment waived, recovery **execution** (`retry-step`, `resume-current-step`, `re-run-mail-attempt`), and audit-only recovery record.

### Mission Control (read-only, Phase MCC-1)

All `GET` under `/internal/admin/mission-control/` — same admin secret.

| Path | Purpose |
|------|---------|
| `/overview` | SQL counts + sampled `build_home_summary` aggregates (stalled / waiting_on / recovery) |
| `/workflows` | Filtered workflow list enriched with `build_home_summary` fields |
| `/workflows/{id}` | Session, steps, full `get_state`, `build_home_summary`, metadata, admin audit rows |
| `/exceptions` | Operator queue (failed / stalled / recovery / mail / responses / reminders) |
| `/responses` | Recent intake rows; `needs_review_only=true` filters review-oriented rows |
| `/reminders` | Global reminder list; optional `status=eligible,queued,...` |
| `/audit` | `workflow_admin_audit` list; optional `workflow_id` |

## Response envelope

```json
{
  "actionResult": "ok | rejected | error",
  "workflowState": { },
  "stepStatus": [ ],
  "userMessage": "…",
  "nextAvailableActions": [ ],
  "asyncTaskState": null,
  "error": null
}
```

## Linear steps

`upload` → `parse_analyze` → `review_claims` → `select_disputes` → `payment` → `letter_generation` → `proof_attachment` → `mail` → `track`

Registry: `services/workflow/registry.py`.

## Stripe ↔ workflow

- Checkout metadata **must** include `workflow_id` (`stripe_client.create_checkout_session` enforces this).
- **Webhook** (`webhook_handler.py`): on `checkout.session.completed`, credits entitlements and calls `notify_payment_completed` when `workflow_id` is present and owned by the user.
- **Streamlit return URL** (`app.py`): after verifying the session, the same `notify_payment_completed` runs so the payment step advances even if the user lands before the webhook (idempotent if already completed).

## Launch validation

```bash
python scripts/workflow_launch_validate.py
# Optional DB smoke:
set WORKFLOW_LAUNCH_VALIDATE_DB=1
python scripts/workflow_launch_validate.py
```

Pytest: `tests/test_workflow_launch_readiness.py`.

**Operational E2E (Phase 3D):** see [WORKFLOW_OPERATIONAL_RUNBOOK.md](./WORKFLOW_OPERATIONAL_RUNBOOK.md) and `scripts/workflow_e2e_verify.py`.

## Versioning

`definition_version` / `engine_version` on `workflow_sessions` — migrate when registry or engine rules change (no automatic migration in this doc).
