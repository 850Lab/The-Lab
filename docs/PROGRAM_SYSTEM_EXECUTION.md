# Program–system execution (locked D1–D18 + revenue-first build plan)

**Purpose:** Repo-controlled copy of the locked product–system–revenue decisions and the BUILD-READY execution plan (slices S1–S6, phased). Use this as the single reference when implementing Phase 1 in code.

**Execution status (this repository)**

| Item | Status |
|------|--------|
| Planning artifact in `docs/PROGRAM_SYSTEM_EXECUTION.md` | Done |
| Phase 1 code — **S1** (orgs + memberships + org API routes) | **Shipped** — `organizations`, `organization_memberships`; `services/org_service.py`; org routes under `/api/orgs` |
| Phase 1 code — **S2** (program enrollment) | **Shipped** — table `organization_program_enrollments`; `services/program_enrollment_service.py`; `POST/GET /api/orgs/{id}/enrollments`; `GET /api/me/org-program` |
| Phase 1 code — **S3** (participant report → findings) | **Shipped** — `reports.organization_id` + `organization_program_enrollment_id`; `services/me_org_report_service.py`; `POST /api/me/report`, `POST /api/me/report/analyze`, `GET /api/me/report/findings`; reuses `process_uploaded_reports` + `extract_claims`/`compress_claims` |
| Phase 1 code — **S4** (dispute selection + letters) | **Shipped** — table `organization_program_dispute_selections`; `services/me_org_dispute_service.py`; `GET /api/me/dispute-options`, `GET/POST /api/me/dispute-selections`, `POST /api/me/generate-letters`; reuses `customer_dispute_strategy` + `process_dispute_pipeline` (no workflow step advance) |
| Phase 1 code — **S5A** (program progress, thin) | **Shipped** — table `organization_program_progress`; `services/program_progress_service.py`; `GET /api/me/progress`; milestones updated from S2 enrollment + S3/S4 routes (not `workflow_sessions`; no instructor/dual-state) |
| Phase 1 code — **S5B** (instructor + dual-state) | **Shipped** — override columns on `organization_program_progress`; `build_effective_milestone_flags` + pause gates on participant POSTs; instructor-only `GET/POST /api/orgs/{id}/participants*` |
| Phase 1 code — **S6** (org visibility) | **Shipped** — `services/org_program_visibility_service.py`; `GET /api/orgs/{id}/progress`, `GET /api/orgs/{id}/outcomes` (aggregate counts, non-PII) |
| Phase 2 — **Participant web UI** (org program) | **Shipped** — `web/src/pages/program/*`, `ProgramShell`, `lib/orgProgramApi.ts`; routes `/program` … `/program/progress`; uses existing auth + `/workflow-api` proxy |

**Related docs:** [WORKFLOW_API.md](WORKFLOW_API.md) (includes **Org program (Phase 1)** route table + auth notes), [WORKFLOW_OPERATIONAL_RUNBOOK.md](WORKFLOW_OPERATIONAL_RUNBOOK.md)

---

# Product–system–revenue alignment (decision lock)

## Method (no separate layers)

Each item is one **decision**, merged with **program**, **system**, and **revenue** in the same row. **Status:** all 18 are **locked** as recorded below.

---

## FINAL 18 DECISIONS (CLEAN + LOCKED)

Use this exactly.

### D1 — North-star outcome

**Chosen:**

B) Tradeline/deletion outcomes (optimized via dispute throughput)

### D2 — Completion rule

**Chosen:**

A) Time-boxed end date (6-month program with structured sessions/classes)

### D3 — Primary buyer

**Chosen:**

Community organizations

### D4 — Org visibility into individuals

**Chosen:**

B/C Hybrid:

Users: full personal data

Instructors: workflow + guided data access

Orgs: progress + outcome visibility (no raw report/PII)

Admin (you): full system visibility

### D5 — Program format

**Chosen:**

C) Hybrid (organization-controlled delivery model)

### D6 — Standard duration (V1)

**Chosen:**

B/C Hybrid:

30–45 days per round

3–6 rounds expected

Program container: 6 months

Additional rounds handled outside core program

### D7 — Milestone miss policy

**Chosen:**

C) Instructor override required (with system nudges + escalation)

### D8 — Who initiates disputes (accountability)

**Chosen:**

C) Flexible execution model (tier + org-config driven)

User-initiated (guided default)

Instructor-led option

Done-for-you option

Submitter-of-record tracked per action

### D9 — Source of truth: human vs. engine

**Chosen:**

C) Dual status with official gating state

### D10 — Workflow enforcement

**Chosen:**

A) Backend-enforced state machine

### D11 — Instructor tenancy

**Chosen:**

A) One org per instructor (V1 constraint)

### D12 — Multi-org end user

**Chosen:**

A) Forbidden in V1

### D13 — Minimum observability (V1)

**Chosen:**

C) Full coach timeline

### D14 — Accountability mechanics owner

**Chosen:**

A) Platform-default playbooks

### D15 — Payments ↔ access

**Chosen:**

C) Hybrid (org-configurable billing models)

### D16 — Tiers in V1

**Chosen:**

C) Three+ tiers (guided / instructor-led / done-for-you)

### D17 — Messaging audit

**Chosen:**

A) In-app only for coaching communication (auditable thread)

### D18 — Automation failure semantics

**Chosen:**

Hybrid (A + B):

Retry + alert

Human queue required for unresolved failures

---

## STEP 2 — Alignment table (program → system → revenue)

Below: **User** / **Org** = program impact. **System** = concrete build surface. **Revenue** = pricing, conversion, retention, scale. Each subsection is **keyed to the locked choice** above.

### D1 — North-star outcome

- **Locked:** Tradeline/deletion outcomes, optimized via dispute throughput.
- **Program — User:** Progress and “wins” tied to removals/updates and the dispute actions that drive them.
- **Program — Org:** ROI narrative emphasizes deletions/tradeline outcomes; throughput supports operational scale story.
- **System — Data:** Outcome records linked to tradelines/items; dispute/action counts; baselines and remeasures for deletions.
- **System — Workflow:** Gates and success semantics align with outcome types + throughput milestones.
- **System — API:** Org-facing metrics exclude raw report where D4 applies; include outcome + throughput summaries.
- **System — Permissions:** Per D4 role matrix for who sees outcome detail vs. aggregates.
- **System — Events:** `outcome_recorded`, `tradeline_outcome_updated`, `dispute_action_completed`, throughput funnel events.
- **Revenue:** Supports outcome-based proof packs; throughput helps margin story; retention tied to visible deletions.

### D2 — Completion rule

- **Locked:** Time-boxed end date; 6-month program with structured sessions/classes.
- **Program — User:** Clear calendar boundary; experiences structured sessions/classes within the container.
- **Program — Org:** Contract, renewals, and comms align to 6-month container + session schedule.
- **System — Data:** `program_container_start/end` (6 months); session/class entities or schedule slots linked to cohort/org config.
- **System — Workflow:** Terminal state at container end; optional per-session attendance or completion markers if product requires.
- **System — API:** Completion and renewal; session roster APIs if applicable.
- **System — Permissions:** Who may extend container or mark sessions complete (platform vs. org admin).
- **System — Events:** `program_completed`, `session_completed`, `container_extended`.
- **Revenue:** Finite 6-month SKU + renewal; conversion via clear end date; scalability via repeatable session templates.

### D3 — Primary buyer context

- **Locked:** Community organizations.
- **Program — User:** Trust, consent, and tone fit community context (not employer-only HR framing).
- **Program — Org:** Buyer is community org; implementation story and materials match that ICP.
- **System — Data:** Org profile type `community_org`; consent and disclosure artifacts appropriate to that channel.
- **System — Workflow:** Intake and optional partner branding for community delivery.
- **System — API:** Org profile drives defaults (comms, optional fields).
- **System — Permissions:** Same four-layer visibility as D4; community admin roles as org admins.
- **System — Events:** `org_onboarded`, `consent_accepted`, buyer_segment=`community`.
- **Revenue:** Pricing and grants/partnerships common in community channel; pipeline tags for community vs. other segments later.

### D4 — Org visibility into individuals

- **Locked:** Users full personal data; instructors workflow + guided access; orgs progress + outcomes without raw report/PII; platform admin full visibility.
- **Program — User:** Understands org sponsor sees progress/outcomes, not full credit file.
- **Program — Org:** Dashboards for engagement and outcomes without handling raw bureau data in sponsor view.
- **Program — Instructor:** Coaching surfaces combine workflow state + guided data (not necessarily full raw export to org).
- **System — Data:** Field-level policy per role; redacted org views; full user self-view; admin audit views.
- **System — Workflow:** Org APIs never return raw report fields; instructor boundary enforced in queries.
- **System — API:** Separate resources: `UserSelf`, `InstructorUserView`, `OrgUserSummary`, `AdminUserView`.
- **System — Permissions:** Four explicit roles (end user, instructor, org admin/staff, platform admin) with matrix tests.
- **System — Events:** `org_viewed_user_summary`, `instructor_viewed_user`, `admin_viewed_user` (audit granularity per policy).
- **Revenue:** Privacy posture enables community partnerships; fewer legal blocks; premium for deeper org analytics without PII.

### D5 — Delivery format

- **Locked:** Hybrid; organization-controlled delivery model.
- **Program — User:** May see cohort-style or rolling elements depending on org configuration.
- **Program — Org:** Chooses how to run delivery (schedule, cohorts, pacing) within platform rules.
- **System — Data:** Org delivery profile: cohort ids, rolling flags, org-defined schedules.
- **System — Workflow:** Engine supports both cohort deadlines and per-user pipelines selected per org template.
- **System — API:** Org-config endpoints for delivery mode; enrollment respects org template.
- **System — Permissions:** Org admin configures delivery; instructors operate within assigned org scope (D11).
- **System — Events:** `delivery_profile_updated`, `cohort_started`, `user_enrolled`, mixed timer events.
- **Revenue:** Enterprise-style configurability supports higher ACV; more test surface for engineering.

### D6 — Standard duration

- **Locked:** 30–45 days per round; 3–6 rounds expected inside 6-month container; extra rounds outside core program.
- **Program — User:** Expects multiple rounds within the journey; clarity on what “core” includes vs. add-on rounds.
- **Program — Org:** Packaging can sell core vs. extended rounds separately.
- **System — Data:** `round_index`, `round_start/end`, link to program container; flag for out-of-core rounds.
- **System — Workflow:** Escalations and nudges per round; D7 overrides apply per gate.
- **System — API:** Round lifecycle; entitlement check for core vs. additional round SKUs (ties D15).
- **System — Permissions:** Who starts/stops a round; org vs. platform.
- **System — Events:** `round_started`, `round_completed`, `extra_round_purchased` (if applicable).
- **Revenue:** Upsell additional rounds; core program bounded for predictable delivery cost.

### D7 — Milestone miss policy

- **Locked:** Instructor override required; system nudges + escalation.
- **Program — User:** Gets nudges; unblocked only via instructor override path when gates block.
- **Program — Org:** Sees stalled users and resolution via coaching, not silent skips.
- **System — Data:** Gate state, override reason, instructor id, timestamp (audit).
- **System — Workflow:** Backend blocks illegal transitions; override is a first-class transition with prerequisites.
- **System — API:** `request_override`, `apply_override`; escalation webhooks or notifications.
- **System — Permissions:** Only instructor (or role you define) can override; org cannot override raw report access (D4).
- **System — Events:** `gate_blocked`, `nudge_sent`, `escalation_triggered`, `gate_overridden`.
- **Revenue:** DFY/instructor-led tiers justify human intervention; fewer chargebacks from stuck users.

### D8 — Dispute initiation authority

- **Locked:** Tier + org-config flexible model; guided default user-initiated; instructor-led and DFY options; submitter-of-record per action.
- **Program — User:** Default path is self-serve guided; higher tiers/org settings enable more done-for-you.
- **Program — Org:** Contract tier defines allowed execution modes for their members.
- **System — Data:** `execution_mode` per org/enrollment/tier; `submitter_of_record` on every dispute action; optional delegation grants.
- **System — Workflow:** State machine branches validate allowed actor for the tier (D16).
- **System — API:** On-behalf-of and impersonation patterns with strict authz; feature errors reference tier upgrade.
- **System — Permissions:** Capabilities matrix: user submit, instructor submit-on-behalf, DFY batch queue.
- **System — Events:** `dispute_drafted`, `dispute_submitted`, `submitter_recorded`, `mode_violation_blocked`.
- **Revenue:** Three+ SKUs map cleanly; upsell from guided to DFY; attribution supports compliance.

### D9 — Source of truth (human vs. engine)

- **Locked:** Dual status with official gating state.
- **Program — User:** UI shows engine vs. coach context where useful; one “official” status drives what they can do next.
- **Program — Org:** Reports use official gating state for consistency.
- **System — Data:** Persist engine-derived fields, instructor fields, and `official_gating_state` (or equivalent) with rules for transitions.
- **System — Workflow:** Automations and API gates read only `official_gating_state` unless admin exception documented.
- **System — API:** Read contracts document which field is authoritative for clients; writes restricted by role.
- **System — Permissions:** Who may set official state vs. add instructor notes.
- **System — Events:** `engine_status_changed`, `instructor_status_changed`, `official_gating_state_set`.
- **Revenue:** Reduces “system said / coach said” refunds; trust and retention.

### D10 — Workflow enforcement model

- **Locked:** Backend-enforced state machine.
- **Program — User:** Cannot rely on UI alone; server rejects invalid progression.
- **Program — Org:** Predictable, enforceable program delivery.
- **System — Data:** State machine definitions per program template (D5/D6); versioning.
- **System — Workflow:** All mutating operations validate current state + role + tier (D8/D16).
- **System — API:** Documented state graph; idempotent transitions; clear error codes.
- **System — Permissions:** Who may admin-reset state (platform vs. designated org role).
- **System — Events:** `state_transition`, `invalid_transition_attempt`.
- **Revenue:** Premium “guaranteed path” positioning; fewer support incidents from illegal paths.

### D11 — Instructor tenancy

- **Locked:** One org per instructor (V1).
- **Program — User:** Dedicated coach within their org context.
- **Program — Org:** Simple mapping: instructors belong to one org.
- **System — Data:** Enforce instructor–org cardinality V1 (single org id on instructor principal).
- **System — Workflow:** Queues and rosters always within that org.
- **System — API:** No cross-org instructor listing without platform admin.
- **System — Permissions:** Instructor claims include single `org_id`.
- **System — Events:** `instructor_assigned` scoped to org.
- **Revenue:** Simpler ops and sales story for V1; future multi-org is a deliberate expansion.

### D12 — End user in multiple orgs

- **Locked:** Forbidden in V1.
- **Program — User:** One active community program enrollment at a time (or strict single-org rule you define).
- **Program — Org:** No cross-org leakage of participant progress.
- **System — Data:** Unique active enrollment per user V1 (or explicit switch-not-supported).
- **System — Workflow:** No shared state across orgs for same user.
- **System — API:** Tenant scoping on all user resources; reject second active org enrollments.
- **System — Permissions:** Session tied to one org context.
- **System — Events:** `enrollment_rejected_duplicate_org` (if applicable).
- **Revenue:** Lower support and engineering risk; clear upsell path when V2 allows multi-org.

### D13 — Observability depth

- **Locked:** Full coach timeline.
- **Program — User:** Rich activity history (within privacy rules).
- **Program — Org:** Strong operational visibility (within D4 redaction).
- **Program — Instructor:** Full timeline for coaching (workflow + messages D17).
- **System — Data:** Append-only or versioned event stream; retention policy; link events to user, org, round, session.
- **System — Workflow:** Notifications and dashboards consume same event stream.
- **System — API:** Query/export endpoints with role-based filters; pagination for long histories.
- **System — Permissions:** Timeline respects D4 (org sees non-PII slice).
- **System — Events:** Comprehensive lifecycle: enroll, session, upload, parse, violation, dispute actions, messages, overrides, failures, outcomes.
- **Revenue:** Justifies higher tiers; higher storage and compliance cost—price accordingly.

### D14 — Accountability owner

- **Locked:** Platform-default playbooks.
- **Program — User:** Consistent cadence of nudges and escalations unless org-specific copy later.
- **Program — Org:** Predictable behavior across customers V1.
- **System — Data:** Central playbook definitions; versioned templates.
- **System — Workflow:** Schedulers reference platform templates; org-specific overrides deferred unless product adds them.
- **System — API:** Internal admin to update playbooks; optional read-only org visibility of schedule type.
- **System — Permissions:** Only platform roles edit playbooks V1.
- **System — Events:** `reminder_sent`, `escalation_triggered`, `playbook_version`.
- **Revenue:** Faster V1 ship; later upsell “custom playbooks” if moved off A.

### D15 — Payments ↔ access

- **Locked:** Hybrid; org-configurable billing models.
- **Program — User:** Clear entitlement state regardless of whether org is subscription, per-seat, or hybrid.
- **Program — Org:** Sales can match community funding models (grant, sponsor, member-pay).
- **System — Data:** `billing_model` per org; entitlements abstraction over subscriptions, seats, program purchases.
- **System — Workflow:** All sensitive actions check entitlement; grace and dunning per model.
- **System — API:** Webhooks from payment providers; mapping layer to internal entitlements; org admin billing views.
- **System — Permissions:** Billing admin vs. coach vs. member.
- **System — Events:** `entitlement_granted`, `seat_consumed`, `payment_failed`, `billing_model_changed`.
- **Revenue:** Conversion across diverse buyers; engineering cost of multiple webhook paths.

### D16 — Tiers in V1

- **Locked:** Three+ tiers — guided / instructor-led / done-for-you.
- **Program — User:** Feature set and human touch increase with tier.
- **Program — Org:** SKUs map to community budget and service level.
- **System — Data:** `tier` on enrollment/org contract; entitlements bitmask or capability flags.
- **System — Workflow:** Branch allowed actors and automations by tier (D8); DFY queues on top tier.
- **System — API:** Central feature guard; consistent error payloads for upgrades.
- **System — Permissions:** Capability matrix per tier (submit modes, override limits, message volume if metered).
- **System — Events:** `tier_assigned`, `upgrade_requested`, `feature_denied`.
- **Revenue:** ARPU expansion; test matrix cost—automate tier tests.

### D17 — Messaging audit

- **Locked:** In-app only for coaching communication; auditable thread.
- **Program — User:** Knows coach chat is logged for quality and compliance.
- **Program — Org:** May receive activity summaries without raw message PII where D4 requires (define explicitly in implementation).
- **Program — Instructor:** Primary user of threads; full thread access in instructor role.
- **System — Data:** Message store with thread id, participants, retention, search indices as needed.
- **System — Workflow:** Link threads to users, rounds, milestones; optional SLAs on instructor reply (playbook D14).
- **System — API:** Thread CRUD, read receipts, moderation hooks if needed.
- **System — Permissions:** Org cannot access full message content if policy says summaries only; align with D4.
- **System — Events:** `message_sent`, `thread_opened`, `thread_exported` (if ever allowed).
- **Revenue:** Auditability supports enterprise/community partnerships; storage cost in pricing.

### D18 — Automation failure semantics

- **Locked:** Retry + alert; human queue for unresolved failures.
- **Program — User:** Sees transparent failure state and path (wait for fix vs. coach takeover).
- **Program — Org:** Visibility into cohort/job health without exposing sensitive internals.
- **System — Data:** Job status, retry counts, DLQ, assignment to human queue, incident correlation ids.
- **System — Workflow:** Automatic retries with backoff; escalate to human queue when exceeded; never silent drop.
- **System — API:** Instructor/admin queue endpoints; retry/resubmit actions with audit.
- **System — Permissions:** Who may acknowledge, reassign, or force-skip (align with D7/D10).
- **System — Events:** `job_failed`, `retry_scheduled`, `human_queue_assigned`, `failure_resolved`.
- **Revenue:** Trust and retention; operational cost of human queue—price DFY/instructor tiers to cover.

---

## STEP 3 — Critical path summary (post-lock)

| ID | Status |
|----|--------|
| D1–D18 | **LOCKED** — execute **BUILD-READY EXECUTION PLAN** below (S1–S6, phased) |

---

# BUILD-READY EXECUTION PLAN (revenue-first, 30–60 days)

Scope discipline: **critical path only** for Phase 1. No advanced dashboards, no full messaging product (D17 deferred), no full automation/scheduling platform. Aligns with locked D1–D18; where a decision implies a large surface (e.g. D13 full timeline, D14 playbooks), Phase 1 delivers **contracting data + events** so Phase 2 can complete the experience without rework.

## SECTION 1 — Core Flows (critical path only)

1. **Org onboarding** — Platform operator creates org record, sets org admin and assigned instructor, sets `billing_model` + `tier` (manual entry acceptable). Community-org profile fields stored (D3).
2. **User enrollment** — Org admin invites member; member accepts; account bound to **one** org; active entitlement flag (manual OK) (D12, D15).
3. **Credit report upload** — Member uploads file; stored as org-scoped artifact; access per D4 views.
4. **Parse + analysis** — Async job: parse report, persist structured result + violations list; failures retry then land in human queue (D18 minimal: bounded retries + operator flag).
5. **Guided dispute selection** — Member selects dispute targets from violations; **guided** tier is default path; `submitter_of_record` = member on generate/submit actions (D8 default).
6. **Letter generation** — System generates dispute letters from selections; artifacts stored; counts toward **dispute throughput** proxy for outcomes until deletion data is backfilled (D1).
7. **Basic progress tracking** — Step-based status derived from **official gating state** (D9, D10); org sees non-PII progress + coarse outcome indicators (letters generated count / manual outcome flags) (D4).

---

## SECTION 2 — Implementation Slices (6 verticals)

### Slice S1 — OrgTenancy_RBAC_Entitlements

**Description:** Minimum multi-tenant shell so a real community org exists with correct role boundaries and sellable configuration fields.

**User action:** Platform admin creates org, assigns org admin and instructor; org admin can view org settings.

**Backend processing:** Persist org; create memberships; enforce instructor **single-org** binding (D11); attach `billing_model`, `tier`, stub `delivery_profile` (D5 hybrid org-controlled — V1 = stored flags, not a builder UI).

**Data model:** `organization`, `org_membership` (role: `platform_admin` | `org_admin` | `instructor` | `member`), `org_settings` (`billing_model`, `tier`, `delivery_profile_json`, `buyer_segment=community`).

**API endpoints (indicative):** `POST /admin/orgs`, `GET /admin/orgs`, `GET/PATCH /orgs/{orgId}` (scoped), `POST /orgs/{orgId}/members` (assign roles), `GET /me/context`.

**Workflow state changes:** None beyond org lifecycle (active org).

**Events emitted:** `org_onboarded`, `tier_assigned`, `entitlement_granted` (manual grant OK), `instructor_assigned`.

**Decisions covered:** D3, D4 (role matrix + future view scoping), D5, D11, D15 (entitlement record, manual), D16 (tier stored).

**Definition of done:** One org can be created manually; org admin and instructor log in with correct org scope; member cannot exist without org; API responses are org-scoped.

**Out of scope:** Self-serve signup, payment webhooks, billing portal UI, multi-org instructor, org analytics dashboards.

---

### Slice S2 — MemberEnrollment

**Description:** Invite/accept path for real users under exactly one org (V1).

**User action:** Org admin sends invite email (or shares token link); member completes registration / accept.

**Backend processing:** Invite token validation; create `user` + `org_membership` as `member`; **reject** second active org enrollment (D12); attach optional `program_enrollment` with `program_container_start/end` (manual dates for D2 six-month box — no class scheduler in Phase 1).

**Data model:** `invitation`, `user`, `org_membership`, `program_enrollment` (dates, `round_index` optional static `1`).

**API endpoints:** `POST /orgs/{orgId}/invitations`, `POST /invitations/{token}/accept`, `GET /orgs/{orgId}/members` (org admin).

**Workflow state changes:** `invited → active_member`.

**Events emitted:** `user_enrolled`, `invitation_sent`, `enrollment_rejected_duplicate_org` (on violation).

**Decisions covered:** D2 (dates only), D4 (member self-view full data policy starts here), D12, D15 (member must be `entitled` boolean or seat consumed — manual OK).

**Definition of done:** First real member completes invite → login → appears on org roster; cannot join second org while active.

**Out of scope:** Bulk CSV, SSO, automated seat billing sync.

---

### Slice S3 — ReportIngest_Parse_Violations

**Description:** Upload → parse → violations using existing 850 Lab engine; durable job + visibility.

**User action:** Member uploads credit report file.

**Backend processing:** Store artifact (org/user scoped); enqueue parse; persist violations; on failure: **retry + alert** then **human queue** record for operator/instructor triage (D18 thin slice).

**Data model:** `report_upload`, `parse_job` (status, attempts, `human_queue_reason`), `parse_result`, `violation` (or engine-equivalent entities).

**API endpoints:** `POST /users/{userId}/reports` (authz: self or instructor/admin per D4), `GET /reports/{id}/status`, `GET /reports/{id}/violations`.

**Workflow state changes (official):** Valid transitions only via S5 rules — typically `… → report_uploaded → parsing → parsed_ok | parse_failed`.

**Events emitted:** `upload_received`, `parse_started`, `parse_completed`, `parse_failed`, `retry_scheduled`, `human_queue_assigned`, `violation_detected`.

**Decisions covered:** D4 (who can upload/view raw), D9 (store `engine_parse_status` vs `official_gating_state` — official advances on `parsed_ok` rule), D10 (transitions validated server-side), D13 (event stream for later timeline), D18.

**Definition of done:** Member upload completes; violations visible to member + instructor views; org cannot fetch raw report via org endpoints (D4).

**Out of scope:** Advanced file types, automated bureau pull integrations, rich virus pipeline.

---

### Slice S4 — GuidedDisputeSelection_LetterGeneration

**Description:** Member selects disputes and receives generated letters; records throughput and submitter (guided default).

**User action:** Member selects items; requests letter generation; downloads or views letters.

**Backend processing:** Persist selections; invoke existing letter generation; store outputs; set `submitter_of_record` on actions (member for guided); enforce **tier capability**: Phase 1 may only enable **guided** execution mode unless org `tier` allows otherwise (stub higher tiers as “contact support”) (D16, D8).

**Data model:** `dispute_selection`, `generated_letter` (file ref, version), `dispute_action` (actor, `submitter_of_record`, timestamp).

**API endpoints:** `POST /users/{userId}/disputes/selections`, `POST /users/{userId}/disputes/letters:generate`, `GET /users/{userId}/disputes/letters`.

**Workflow state changes:** `parsed_ok → disputes_selected → letters_generated` (official states named to match product copy).

**Events emitted:** `dispute_drafted`, `letter_generated`, `submitter_recorded`, `official_gating_state_set` (advance).

**Decisions covered:** D1 (throughput + letter artifacts as proxied outcomes), D8 (guided default + submitter tracking), D9 (official advance), D10, D16 (tier gate on execution mode), D4.

**Definition of done:** Guided user completes selection + letter generation E2E; org API shows **counts** / step complete without PII (via S6 reads).

**Out of scope:** Auto-mail, DFY batch generation queues, instructor-initiated on-behalf flows (Phase 2 unless tier forces minimal endpoint).

---

### Slice S5 — WorkflowEngine_OfficialGating_InstructorOverride

**Description:** Single backend authority for allowed transitions, dual engine vs coach signals, and instructor override with audit (D7, D9, D10).

**User action:** Member attempts step progression; instructor applies override with reason when user is blocked or stalled.

**Backend processing:** Central transition service: `(current_official_state, action, actor_role, tier)` → next state or 409; persist `engine_*` and `coach_*` fields where applicable; `official_gating_state` is **only** field that gates APIs; override writes audit row (D7).

**Data model:** `workflow_instance` (per user program), `official_gating_state`, optional `engine_status`, `coach_status`, `override_record` (reason, actor, timestamps).

**API endpoints:** `GET /users/{userId}/workflow`, `POST /users/{userId}/workflow:transition` (member), `POST /users/{userId}/workflow:override` (instructor), `GET /users/{userId}/workflow/audit` (instructor/admin).

**Workflow state changes:** Minimal Phase 1 graph (example): `enrolled → report_pending → report_uploaded → parsing → parsed_ok → disputes_pending → disputes_selected → letters_pending → letters_generated → round_complete_stub` (last can map to “ready for outcomes” without automating D6 rounds).

**Events emitted:** `state_transition`, `invalid_transition_attempt`, `gate_blocked`, `gate_overridden`, `engine_status_changed`, `coach_status_changed`, `official_gating_state_set`.

**Decisions covered:** D7, D8 (who may transition on behalf — Phase 1: mostly member; override unlocks), D9, D10, D11 (instructor scoped to org), D4.

**Definition of done:** Invalid transitions rejected with stable error codes; instructor override works with immutable audit; all slices call the same transition guard.

**Out of scope:** Automated nudges/escalations (D14 execution), complex branching per delivery profile UI.

---

### Slice S6 — OrgNonPIIProgress_OutcomeSignals

**Description:** Org-facing visibility: progress + outcome **signals** without raw report (D4, D1).

**User action:** Org admin opens summary list of members.

**Backend processing:** Aggregate per user: current `official_gating_state`, step index, `letters_generated_count`, optional `outcome_signal` fields (manual instructor entry OK for deletions until automated).

**Data model:** Read models or views: `org_member_progress_summary` (no raw fields).

**API endpoints:** `GET /orgs/{orgId}/members/progress`, `GET /orgs/{orgId}/members/{userId}/summary` (non-PII contract).

**Workflow state changes:** Read-only.

**Events emitted:** `org_viewed_user_summary` (optional audit).

**Decisions covered:** D1 (outcome/threshold storytelling at org layer), D4 (org boundary), D13 (Phase 1 = events + summaries; **full coach timeline UI** = Phase 2), D2/D6 reporting labels only.

**Definition of done:** Org admin sees each member’s step + coarse signals; never receives raw bureau payload via these endpoints.

**Out of scope:** Dashboard builder, exports, BI warehouse.

---

## SECTION 3 — Phased execution plan

### Phase 1 — REQUIRED TO SELL + DELIVER FIRST USERS

Absolute minimum working system for **one paying community org**:

- **Build order:** S1 → S2 → S5 (skeleton + `enrolled`/`report_pending`) → S3 → S4 → S5 (wire all transitions) → S6.
- **Manual/mocked acceptable:** Org creation; billing; seat counts; program dates; outcome deletions (manual flag); nudges via email off-platform; D17 messaging = **no product** (email/SMS outside app OK for Phase 1).
- **Locked decisions satisfied enough to sell:** D10 (server enforcement), D9 (official gating), D4 (four-view API contract), D8 guided + submitter record, D1 throughput proxy, D11–D12, D15 hybrid (manual entitlement), D16 (tier field + guided path), D18 (parse retry + queue record), D3 (org type field).

### Phase 2 — REQUIRED TO SCALE DELIVERY

After first orgs/users:

- **Tier branching (D16/D8):** instructor-led and DFY execution modes, on-behalf APIs, queue for DFY work items.
- **D13 completion:** Instructor “full timeline” read API + UI from existing events; retention policy.
- **D7/D14 operations:** In-app or email nudges from platform playbooks (scheduler); escalation rules.
- **D15:** At least **one** real payment webhook → entitlement automation for chosen model.
- **D18:** Operator/instructor queue UI for stuck jobs, not only DB flags.
- **D6:** Multiple `round_index` transitions + optional “extra round” entitlement check (still avoid heavy scheduling product if not needed).

### Phase 3 — ENHANCEMENTS (non-blocking)

- **D17:** In-app audited coaching threads (replace external comms where required).
- **Advanced dashboards / exports** for orgs.
- **D5** rich org delivery builder (cohort vs rolling configuration UI).
- **D2** structured sessions/classes entities if sales require scheduling inside product.

---

**Explicitly excluded from this execution plan (per prompt):** advanced dashboards (Phase 1), full messaging (Phase 1), full automation platform (Phase 1), exhaustive edge-case handling — reintroduce only via Phase 2/3 above.
