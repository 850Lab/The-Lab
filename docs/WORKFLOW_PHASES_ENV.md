# Workflow phases: environment checklist

This document maps each **consumer dispute** linear step (`services/workflow/registry.py` → `DISPUTE_STEP_DEFINITIONS`) to the **server and client settings** needed so the phase works in **local dev**, **automated tests**, **staging**, and **production (e.g. Railway)**.

The React app talks to the workflow API via `VITE_WORKFLOW_API_URL` or the dev proxy; see `web/src/lib/apiBase.ts`.

---

## One table: step → dependencies

| Step (head) | What must work | Required / critical env |
|-------------|----------------|-------------------------|
| **upload** | Store upload, optional direct-to-S3 | `DATABASE_URL` (or local sqlite experiments: `DB_BACKEND=sqlite` + `WORKFLOW_SQLITE_PATH`). Optional: `REPORT_UPLOAD_S3_*`, `AWS_*` for presigned path. Reverse proxy must allow large bodies (see root `.env.example`). |
| **parse_analyze** | Background job processes PDF | **`WORKFLOW_JOB_WORKER_ENABLED=1`** (default in `api/workflow_app.py`). **Poppler + Tesseract** on the host (Dockerfile includes them). Same DB as above. |
| **review_claims** | Parsed analysis in DB | DB + completed parse job. |
| **select_disputes** | User selections persisted | DB. |
| **payment** | Stripe Checkout + redirect back | **`STRIPE_SECRET_KEY`**, **`STRIPE_PUBLISHABLE_KEY`**. **`WORKFLOW_CUSTOMER_APP_ORIGIN`** or **`PUBLIC_APP_ORIGIN`** — must be the exact customer app base URL (scheme + host, no path); used for `success_url` / `cancel_url`. For webhooks: **`STRIPE_WEBHOOK_SECRET`** on the server that receives Stripe events (`webhook_handler.py`). |
| **letter_generation** | Entitlements + letter run | Stripe + payment step complete (or waived per product rules). |
| **proof_attachment** | Proof UI | Usually no extra secrets; integrity banner may show mail blocked preview if Lob misconfigured (see **mail**). |
| **mail** | Lob certified mail | **`LOB_API_KEY`**. For **test/staging** with a **`test_`** key: set **`REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND`** unset, `0`, or `false` — otherwise customer send is blocked (`lob_client.customer_mail_send_blocked_reason`). For **production** live mail: use a **live** Lob key; you may set `REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND=1` to forbid accidental test keys. |
| **track** | Tracking + responses + escalation | DB; optional **Resend** for mail-related comms (`RESEND_API_KEY`, `RESEND_FROM_EMAIL`). |

**Auth (all steps):** sign-up, verification, session — **`RESEND_API_KEY`**, **`RESEND_FROM_EMAIL`** (or dev patterns described in `.env.example`).

**Admin / Mission Control (operators):** may use **`WORKFLOW_ADMIN_API_SECRET`**, **`WORKFLOW_INTERNAL_API_SECRET`** as documented in your deployment notes.

---

## Local development (full path)

1. **API:** `python -m uvicorn api.workflow_app:app --host 127.0.0.1 --port 8000` (or project scripts).
2. **DB:** Postgres via `DATABASE_URL`, or sqlite for local-only experiments (`DB_BACKEND=sqlite`).
3. **Worker:** leave `WORKFLOW_JOB_WORKER_ENABLED` at default `1` so parse jobs run in-process.
4. **Web:** in `web/`, copy `web/.env.example` → `.env.local` — set `WORKFLOW_API_PROXY_TARGET=http://127.0.0.1:8000` *or* `VITE_WORKFLOW_API_URL=http://127.0.0.1:8000`.
5. **Payment:** Stripe **test** keys (`sk_test_…`, `pk_test_…`); set `WORKFLOW_CUSTOMER_APP_ORIGIN=http://localhost:5173` (or your Vite port).
6. **Mail:** Lob **test** key; **`REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND` unset/false** so the integrity banner does not block mail on test keys.

---

## CI / automated tests

- Prefer **sqlite** or ephemeral DB if tests support it (see `tests/` and env vars used in fixtures).
- Set **`WORKFLOW_JOB_WORKER_ENABLED=0`** only when tests mock jobs explicitly (see e.g. `tests/test_me_report_async_upload_sqlite.py`).
- Stripe/Lob: mock or omit; do not point at production secrets.

---

## Staging / Railway (customer app + API)

**API host (Railway):**

- `DATABASE_URL`, `ENVIRONMENT=production` (or your policy — production mode rejects sqlite).
- `RESEND_API_KEY`, `RESEND_FROM_EMAIL`.
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` — use **test** or **live** keys consistent with your staging policy; match webhook endpoint and `STRIPE_WEBHOOK_SECRET`.
- `WORKFLOW_CUSTOMER_APP_ORIGIN=https://your-staging-app.example.com` (the deployed Vite/static site origin).
- `LOB_API_KEY` — test key for safe staging; leave `REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND` off.
- `WORKFLOW_JOB_WORKER_ENABLED=1` unless you run a **separate worker process** (advanced; default embeds worker in the API process).

**Static front end (e.g. Vercel or Railway static):**

- Build with **`VITE_WORKFLOW_API_URL=https://your-railway-api.up.railway.app`** (no trailing slash).

**Stripe redirect:** success/cancel URLs use `WORKFLOW_CUSTOMER_APP_ORIGIN`; the customer app must be reachable at that origin.

---

## Quick “why is mail blocked?”

If the UI shows mailing paused / Lob configuration:

- Missing or invalid **`LOB_API_KEY`**, or
- **`REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND`** is enabled while the key is still a **`test_`** key.

Admins can bypass live-key enforcement for support; customers cannot.

---

## Related files

- `lob_client.py` — `customer_mail_send_blocked_reason`, `require_live_lob_for_customer_send`
- `services/workflow/integrity_hints_service.py` — surfaces `mailBlocked` to the client
- `web/src/components/WorkflowIntegrityBanner.tsx` — banner when `mailBlocked`
- `api/workflow_app.py` — `WORKFLOW_JOB_WORKER_ENABLED`, payment routes, CORS
- Root `.env.example` — long-form comments and upload limits
- `services/workflow/env_readiness.py` — phase/integration checks; startup logs warnings when any phase is not `ok`
- HTTP: **`GET /health/workflow-readiness`** (public: counts only), **`GET /internal/admin/workflow-env-readiness`** (full detail; `WORKFLOW_ADMIN_API_SECRET`)
