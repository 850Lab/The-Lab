# System Identity Lock Prompt

**Purpose:** Paste this (or reference this file) at the start of planning, architecture, or implementation sessions so assistants and humans stay aligned on what this system **is**, **for whom**, and **what must not be violated**.

---

## Identity (what this system is)

850 Lab is a **backend-authoritative credit workflow and org-program product**: users and organizations move through **report intake → analysis → dispute strategy → letters and follow-on steps** under a **workflow state machine** enforced by the server—not by clients inventing progress.

The **commercial north star** is **the first paying organization**: community-style buyers who need the system to be **usable**, **visible** (cohort and outcomes), and **trustworthy** (clear boundaries, auditability, supportable operations).

---

## Architectural locks (non-negotiable)

1. **Source of progression truth:** `services/workflow/engine` + steps/session in the database. React, Streamlit, and scripts are **clients** unless explicitly designated as trusted internal entrypoints.
2. **Authoritative HTTP API:** `api/workflow_app.py` (+ `api/workflow_deps.py`) for gated customer, internal, and admin routes. **Privileged mutations** (admin overrides, recovery execution, mission control aggregates, etc.) stay behind documented secrets and route patterns—static **launch readiness** checks in `services/workflow/launch_readiness_checks.py` exist to prevent silent drift (import/call-site guards, flow-gate wiring checks).
3. **Flow gates:** Customer payment paths and internal service completion/failure paths go through **`workflow_flow_gates`** assertions on the intended trusted surfaces (hooks, payment service, job worker, workflow API)—not ad hoc skips.
4. **Org program (Phase 1):** Orgs, memberships, enrollments, participant progress (**dual state**: system vs instructor), instructor overrides, and **aggregate** org visibility (`/api/orgs/{id}/progress`, `/outcomes`) are part of the same product story as solo workflow—PII boundaries per locked product decisions (orgs see aggregates, not raw reports, unless policy changes).

Do **not** propose bypassing the engine for “convenience,” wiring admin/recovery modules from random services, or treating client-side state as authoritative for step advance.

---

## User-visible surfaces (what exists in-repo)

| Surface | Role | Notes |
|--------|------|--------|
| **Streamlit (`app.py`)** | Legacy / parallel solo UX | Rich historical UI; demo mode `?nav=demo` (sample “Alex Johnson” path, letter preview). Retirement tracked in `docs/STREAMLIT_RETIREMENT.md`—new business logic belongs in `services/` + API, not Streamlit. |
| **React (Vite `web/`)** | Forward-looking customer + program UX | Participant program under `/program/*`; workflow shell; **public engine demo** at demo experience page. |
| **Public demo (API + React)** | Credible technical proof | `services/public_demo_service.py`: fixture PDFs → **live parser + deterministic dispute strategy + dispute helpers + letters / credit command plan** via dedicated demo user—**not** a fake animation. |
| **Mission Control (React)** | Operator | Includes demo lead list and other operator views backed by admin-authenticated API routes. |

When describing “the demo,” **specify which**: **Streamlit taste demo** vs **React authoritative fixture demo**.

---

## Funnel and onboarding (product + implementation)

- **Acquisition:** Landing and ads (UTM/ref capture on Streamlit landing; ad landing patterns in repo). **Streamlit demo** = fast comprehension; **React public demo** = proof of engine.
- **Lead capture:** `POST /api/public/demo/lead` → `demo_leads`; rate limiting; operator notification; **Mission Control** listing (`McDemoLeads.tsx`). This supports **workshop → org sales** follow-up.
- **Onboarding lanes:** Email-verified signup; solo workflow via API + React; **org** path via `/api/orgs/*`, enrollments, `/api/me/org-program`, `/program/*`; separate **sprint intake** / `sprint_leads` for high-touch capture where implemented.

Do not treat the product as “API only” or “Streamlit only”—describe the **full funnel** when discussing go-to-market or first payer.

---

## Core product capabilities (must be named when discussing “what we sell”)

- **Report pipeline:** Upload, parse, claims extraction/compression, intake summary—shared with org report flows where wired.
- **Dispute / strategy layer:** Deterministic strategy (`dispute_strategy`), **customer dispute strategy** (eligibility, bureaus, metadata-aware filtering), dispute pipeline, selections, **letter generation** (including async jobs), **credit command plan**—these are **legal-strategy-capable** product cores, not side features.
- **Workflow integration:** Letter generation and mail/payment gates participate in **steps, hooks, jobs, and audits** so outcomes are **defensible** and **supportable**.

When asked for scope or roadmap, **anchor** on these engines—not only generic “CRUD” or “dashboard.”

---

## Language assistants must use

- **How** = enforcement, boundaries, checks, gates, where imports/calls may live (operational integrity).
- **What** = shipped UX, APIs, org features, demos, letters, strategy outputs (customer-visible capability).
- **Why** = locked product decisions (e.g. `docs/PROGRAM_SYSTEM_EXECUTION.md`, buyer, dual-state, visibility rules).

Do not collapse **How** work into “the whole product”; it **enables** trust for paying orgs but does not replace **visible org/instructor experience** or **commercial wrapper**.

---

## Default assistant behavior under this lock

1. Prefer changes that **preserve** workflow authority and documented route/auth models.
2. When adding privileged behavior, **place** it behind the same classes of gates as existing admin/internal patterns; consider whether **launch_readiness** should gain a new guard.
3. When discussing demos, **distinguish** Streamlit vs React fixture demo and mention **lead capture** when discussing conversion.
4. When discussing “first paying org,” require **visibility** (progress/outcomes APIs + UI or explicit ops deliverable) and **trust** (privacy, roles, support path)—not only backend completeness.
5. Do not **forget** dispute/strategy/letter/report engines when describing system identity or MVP scope.

---

## One-line lock

**850 Lab is an org-ready, workflow-authoritative credit dispute platform whose demo proves the real report→strategy→letter engine, captures leads for human follow-up, and enforces progression and privilege on the server—optimized for the first paying organization’s need for usability, visibility, and trust.**

---

*File: `docs/SYSTEM_IDENTITY_LOCK_PROMPT.md` — paste the sections above (or the one-line lock + Architectural locks) into system instructions when context is thin.*
