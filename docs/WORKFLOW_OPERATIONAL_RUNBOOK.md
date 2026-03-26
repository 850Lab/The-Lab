# 850 Lab — Operational runbook (Phase 3D)

Repeatable verification of workflow lifecycle, observability, failure handling, and drift. **No new product features** — only execution and checks.

---

## Part 1 — Full lifecycle (automated + manual)

### A. Automated harness (DB + trusted code paths)

From repo root, with PostgreSQL configured like the main app:

```bash
set WORKFLOW_E2E_USER_ID=<existing users.id>
python scripts/workflow_e2e_verify.py
```

Optional failure-injection add-on:

```bash
set WORKFLOW_E2E_FAILURES=1
python scripts/workflow_e2e_verify.py
```

| # | Step | Harness behavior |
|---|------|-------------------|
| 1 | workflow init | `WorkflowEngine.init_workflow` |
| 2 | upload + parse | `notify_upload_and_parse_success` (simulated file metadata) |
| 3 | review | `notify_review_claims_completed` |
| 4 | dispute selection | `notify_select_disputes_completed` (3 bureaus → mail gate = 3) |
| 5 | payment | `service_complete_step(payment)` — **not** real Stripe |
| 6 | letter generation | `service_complete_step(letter_generation)` |
| 7 | proof | `service_complete_step(proof_attachment)` |
| 8 | mail | Three × `notify_certified_mail_sent` (equifax, experian, transunion) |
| 9 | track | Completed by mail hook when gate satisfied |
| 10 | response intake | `intake_bureau_response` with empty `parsed_summary` |
| 11 | classification | Expect `insufficient_to_classify` or stored `classification_status` |
| 12 | reminder candidates | `create_reminder_candidates_for_workflow` |
| 13 | reminder delivery | Queue + `deliver_reminder` → **pass** or **warn** (Resend) / **skip** if no eligible row |
| 14 | recovery | Failure suite: mail fail → `compute_recovery_actions` → `execute_retry_step` |

**Manual (not in harness)**

- **Real Stripe test mode:** Streamlit checkout with `workflow_id` in metadata → return URL and webhook both call `notify_payment_completed` (see `docs/WORKFLOW_API.md`).
- **Real Lob:** send mail from app; compare `metadata.mail` with Lob dashboard.

### B. Manual checklist (staging)

1. Sign in → confirm `ensure_active_workflow_id` matches UI “current” workflow.
2. Upload a real PDF → confirm hooks or workers advance upload/parse (logs: `workflow_audit`, `service_complete`).
3. Complete review + strategy in UI → `select_disputes` + `mail.expected_unique_bureau_sends`.
4. Pay with Stripe test card → entitlements + workflow `payment` completed.
5. Generate letters / proof in UI → internal completes for `letter_generation` / `proof_attachment`.
6. Mail → partial sends update `confirmed_bureaus` without completing `mail` until count satisfied.
7. Track → after gate, `track` completed; overall may become `completed`.
8. Intake a response via API `POST .../responses/intake` with Bearer session.
9. Run reminder worker: `POST /internal/reminders/process-delivery-batch` (internal secret).
10. Admin recovery: `POST /internal/admin/.../recovery/retry-step` (admin secret + body `user_id`).

---

## Part 2 — Observability validation

After each milestone, compare:

| Check | How |
|-------|-----|
| Workflow state vs reality | `GET /api/workflows/{id}/state` (session auth) — `currentStep`, `stepStatus` |
| Home-summary next action | `GET /api/workflows/{id}/home-summary` — `currentStepId`, `nextBestAction`, `waitingOn` |
| No premature advance | Head step in DB matches last successful domain action (no `service_complete` without work) |
| Not stuck incorrectly | If head `in_progress` > SLA, inspect `async_task_state` |
| Async state truthful | `async_task_state.phase` matches worker logs |
| Mail counts | `metadata.mail.confirmed_bureaus` length vs `expected_unique_bureau_sends`; `failed_send_count` on partial failure |
| Reminders | `workflow_reminders` statuses; dedupe via `has_active_or_recent_reminder`; audit `reminder_delivery_*` |
| Admin overrides | `workflow_admin_audit` + `metadata.adminOverrideHistory` |

**Drift rule:** `home-summary.currentStepId` must match engine head unless `linearPhase=done` (both must agree on completion).

Harness records drift strings when `build_home_summary` disagrees with `compute_authoritative_step`.

---

## Part 3 — Failure injection (in harness + manual)

| Scenario | Harness | Expected |
|----------|---------|----------|
| Failed mail send | `notify_mail_send_failed` | `failed_send_count++`, mail `failed`, recovery suggests retry / re-run mail |
| Failed reminder delivery | Resend missing → `deliver_reminder` **warn** | Row `failed`, audit `reminder_delivery_failed` |
| Failed parse | `service_fail_step(parse_analyze)` after upload complete | `overall_status=failed`, `failedStep` in home-summary |
| Incomplete payment | `run_incomplete_payment_stall` | Head stays `payment` |
| Unclear classification | Empty `parsed_summary` intake | `insufficient_to_classify` or classification_status `failed` with manual_review |

**Consistency:** Workflow JSON remains valid; no silent `service_complete` on failure paths without audit.

---

## Part 4 — Drift detection

Watch for:

- **State vs DB:** `workflow_steps.status` out of sync with `workflow_sessions.current_step` / `overall_status` (repair transaction exists in engine load path for linear availability only — investigate if head wrong).
- **User-visible vs engine:** React route vs `home-summary.safeRouteHint` / `currentStepId`.
- **Silent failures:** absence of `workflow_audit` lines for a state change that occurred.
- **Payment:** entitlements granted but `payment` step still `available` → check Stripe metadata `workflow_id` and return-path notify (see Phase 3C).

---

## Part 5 — Deliverables template (fill per run)

Record after each staging run:

1. **Execution steps used** — harness only / harness + manual list above.
2. **Passed cleanly** — step names with `kind=pass`.
3. **Failed / unexpected** — `kind=fail` or `warn` with logs.
4. **Drift** — any non-empty `drift` array from harness JSON.
5. **Fixes applied** — only critical hotfixes (should be rare; prefer tickets).
6. **Confidence** — low / moderate / high (see below).

### Confidence rubric

- **High:** Harness pass + manual Stripe/Lob smoke + no drift + audit complete.
- **Moderate:** Harness pass; manual payment/mail not yet exercised in same environment.
- **Low:** Harness skipped/failed, or drift observed, or secrets missing.

---

## Module reference

- Harness: `services/workflow/e2e_operational_harness.py`
- CLI: `scripts/workflow_e2e_verify.py`
- Invariant checks: `services/workflow/launch_readiness_checks.py` + `scripts/workflow_launch_validate.py`
