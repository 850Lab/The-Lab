# Streamlit retirement (controlled transition)

**Status:** Active — Streamlit is **frozen** for net-new product work.  
**Authoritative surface:** **React** (`web/`) + **FastAPI** (`api/workflow_app.py`).  
**Streamlit role until parity:** **Reference / operator-only** — in production-like deploys the **customer workflow shell is disabled** for non-admins (`services/streamlit_customer_gate.py`); FastAPI + React are the only customer mutation path.

Do not delete `app.py` until the **Deletion criteria** below are satisfied.

---

## 1. Freeze rules (effective now)

| Rule | Meaning |
|------|--------|
| No new product features in Streamlit | New user-facing capabilities ship only via React routes + FastAPI routes + shared services. |
| No new business logic in Streamlit | Logic belongs in importable modules (`services/`, `parsers.py`, `dispute_strategy.py`, etc.) and is invoked from FastAPI (and later React-only clients). |
| Allowed Streamlit edits | Bug fixes that restore broken behavior; refactors that **reduce** duplication by delegating to shared code; parity-support wiring to match API behavior; security fixes. |
| Authoritative orchestration | Workflow progression for the shipped product is **`workflow_sessions` / `workflow_steps`** via `services/workflow/*` and HTTP APIs — not `st.session_state.ui_card` / `panel` for new work. |

Optional dev banner: set `STREAMLIT_LEGACY_REFERENCE_BANNER=1` when running Streamlit to show a caption pointing here.

---

## 2. Parity checklist (before archive/delete Streamlit)

All must be true on **React + FastAPI** (not “documented elsewhere”):

- [ ] **Core linear flow:** upload → parse/analyze → prepare → strategy → payment → letters → proof → mail → tracking (matches `services/workflow/registry.py` + React guard routes).
- [ ] **Demo mode:** React route ``/demo`` + ``GET/POST /api/public/demo/*`` (when ``PUBLIC_DEMO_ENABLED=1``) runs fixtures through the **real** pipeline; Streamlit ``demo_data.py`` can retire once this is deployed and verified in production.
- [ ] **72-hour command plan:** exposed in customer UI (API: `GET /api/workflows/{id}/credit-command-plan`).
- [ ] **Round 2+:** dispute selection and letter generation with `round_number > 1` and `previously_disputed_claim_ids` (Streamlit today; API still round-1-centric in several paths — must be closed).
- [ ] **Post-track / escalation:** response intake, classification, and escalation UX complete (React `EscalationActionPage` must not remain placeholder; parity with Streamlit escalation tools or an intentional narrowed scope **documented and accepted**).
- [ ] **Battle plan / free-tier caps:** same eligibility and per-bureau limits as Streamlit where product requires it (`auth.FREE_PER_BUREAU_LIMIT`, battle-plan style selection if still product-relevant).
- [ ] **Voice profile + PDF/signature pipeline:** if still sold, exposed through API + React (DB + `letter_generator` already exist; Streamlit currently owns the UX).
- [ ] **War Room / strike metrics / mission setup:** port, replace with a smaller dashboard, or **explicitly retire** as product decisions — not silently dropped.
- [ ] **Admin / operator:** Mission Control + org program APIs cover what admins/instructors need, or Streamlit admin is replaced.
- [ ] **Payments:** Stripe return paths and entitlement application tested from React primary entry (Streamlit may remain redirect-only until cutover).
- [ ] **Deployment:** production entry is FastAPI + static React (or equivalent); Streamlit not required for normal customer operations.

---

## 2b. Read-only / retirement execution checklist (control layer + single surface)

Use this **after** parity items in §2 are trending green — it turns Streamlit from “fallback UI” into **non-authoritative** usage without surprise workflow drift.

- [ ] **Inventory Streamlit workflow mutations:** every `workflow_hooks.*`, `WorkflowEngine`, `service_complete` / `service_fail`, Stripe reconcile, and `report_pipeline` entry from `app.py` / `app_backup.py` / `app_real.py` (grep `workflow_hooks`, `WorkflowEngine`, `notify_payment`).
- [ ] **Confirm hooks are gated:** `services/workflow/hooks.py` uses `assert_internal_service_complete_allowed`, `assert_internal_service_fail_allowed`, and payment asserts in `workflow_payment_service` so Streamlit cannot advance the wrong head (same rules as FastAPI + internal HTTP).
- [ ] **No Streamlit-only progression:** any step transition not reachable via FastAPI + React should be **removed or delegated** to shared services called from API routes.
- [x] **Kill-switch / production default:** `services/streamlit_customer_gate.py` — production-like hosts forbid Streamlit customer mutations unless `STREAMLIT_ALLOW_CUSTOMER_MUTATIONS=1`. Hooks no-op Streamlit-branded `audit_source` (exempt `payment_return` for Stripe URL migration). `database.save_report(..., mutation_channel="streamlit")` raises when forbidden. `STREAMLIT_WORKFLOW_MUTATIONS_DISABLED=1` still forces hook blocking in dev.
- [ ] **Production entry:** confirm deploy scripts / Replit / Docker start **FastAPI + React**; Streamlit not in the default customer path.
- [ ] **Delete or archive:** once §2 + this checklist + §4 deletion criteria are satisfied, remove `streamlit` from default deps or move `app.py` to an `archive/` folder per repo policy.

---

## 3. Migration map (Streamlit-only or primary today)

| Capability | Primary Streamlit location | Target (authoritative) | Action |
|------------|---------------------------|-------------------------|--------|
| Demo (`?nav=demo`, Alex Johnson) | `demo_data.py`, `app.py` (session guards), `views/landing.py` | React route + API session or fixture workflow | **Port** — same engine, no fake analysis |
| Card/step orchestration | `app.py` (`ui_card`, `CARD_ORDER`), `ui/stepper.py` | Already: `workflow_engine` + React `workflowStepRoutes.ts` | **Freeze Streamlit**; extend API/registry only |
| Round 2+ letters / comparison | `app.py`, `letter_generator.generate_round2_letter`, DB round columns | `customer_letter_service` + strategy routes + workflow metadata | **Port** — reuse generators from API |
| Battle plan + 72hr UI | `app.py`, `credit_command_plan.py` | API done for plan JSON; Streamlit HTML renderer only | **React UI** for plan; keep `credit_command_plan.py` shared |
| AI strategy preview in disputes | `app.py`, `dispute_strategy.build_ai_strategy` | `build_dispute_strategy_payload` (deterministic + suggestions); LLM parity | **Extend API** if Streamlit LLM path is still product |
| Voice profile + signature PDF | `app.py`, `ui/signature_pad.py`, `letter_generator.generate_letter_pdf` | New API routes + React steps | **Port** when in scope |
| War room / strike metrics | `app.py`, `war_room_plan.py`, `strike_metrics.py` | React dashboard + API aggregate endpoints | **Port or drop** (product decision) |
| Escalation letters (MOV, CFPB, etc.) | `app.py` panels | React `EscalationPage` / complete `EscalationActionPage` + API | **Port** |
| Response / evidence tracker | `app.py`, workflow response services | Partial: `ResponseIntakePage`, `customer_response_service` | **Complete parity** |
| Sprint intake | `views/sprint_intake.py` | TBD route or retire | **Decide** |
| Ad landing / pixels | `views/landing.py` (go), `app.py` | Marketing pages or React | **Port or separate** |
| Admin dashboard | `views/admin_dashboard.py` | Mission Control + DB admin tools | **Replace** over time |
| Auth pages | `views/auth_page.py` | `web/src/pages/LoginPage.tsx`, etc. | **React authoritative** |
| Legal/proof upload page | `views/legal.py` | React proof flow | **React authoritative** |

**Dependency order:** (1) close round-2 + workflow metadata in API, (2) demo on API stack, (3) voice/signature/PDF if required, (4) war room / escalation depth, (5) retire Streamlit admin paths.

---

## 4. Deletion criteria (safe to remove Streamlit)

1. All items in **§2 Parity checklist** are checked and covered by automated or runbook-tested flows.
2. No production deployment uses `streamlit run app.py` as the primary customer entry.
3. Remaining Streamlit-only code paths are either removed or moved to shared modules; **no** unique business logic left only in `app.py`.
4. Team sign-off that admin/instructor/demo needs are met without Streamlit.
5. `pyproject.toml` / Replit / `start.sh` updated so default boot is API + React only.

Until then: **keep** `app.py`, `views/`, `ui/`, `demo_data.py` as reference and fallback.

---

## 5. Inventory: shared vs split (quick reference)

**Shared engines (keep; call from API):** `services/report_pipeline.py`, `services/dispute_pipeline.py`, `services/customer_*`, `parsers.py`, `claims`, `review_claims`, `dispute_strategy.py`, `letter_generator.py`, `credit_command_plan.py`, `database.py`, `auth.py`.

**Authoritative HTTP:** `api/workflow_app.py` (+ `api/workflow_deps.py`).

**Authoritative customer UI:** `web/src/` (Vite app).

**Streamlit shell (frozen):** `app.py` (~7k+ lines), `app_real.py` / backups if still present, `views/*`, `ui/*`, `demo_data.py`.

---

## Related docs

- `docs/WORKFLOW_API.md` — route reference  
- `docs/PROGRAM_SYSTEM_EXECUTION.md` — org program slice (already API-first)
