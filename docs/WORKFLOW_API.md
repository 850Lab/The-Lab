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

## User-facing endpoints (session required)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/workflows/init` | Create session + seed steps (body: optional `workflow_type`, `metadata`) |
| GET | `/api/workflows/{id}/state` | Authoritative state + next actions |
| GET | `/api/workflows/{id}/resume` | Resume-oriented copy |
| GET | `/api/workflows/{id}/home-summary` | Lifecycle, reminders, recovery hints |
| POST | `/api/workflows/{id}/responses/intake` | Bureau/furnisher response intake + classification |
| POST | `/api/workflows/{id}/steps/{stepId}/start` | User starts current step |

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
