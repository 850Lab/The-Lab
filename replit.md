# Parser Machine - 850 Lab

## Authoritative product surface (transition)

**Forward build target:** **React** (`web/`) + **FastAPI** (`api/workflow_app.py`). New product features and workflow rules ship there (and in shared `services/`), not in Streamlit session state.

**Streamlit** (`app.py`): **legacy reference / fallback** until parity criteria in `docs/STREAMLIT_RETIREMENT.md` are met. Streamlit is **frozen** for net-new product work (bug fixes and parity-support changes only).

## Overview
Parser Machine is the foundational module of 850 Lab, a consumer credit report analysis and correspondence platform. Its primary purpose is to process credit report PDFs, extract structured data, identify potential inaccuracies and FCRA violations, and generate precise, factual dispute letters. The project aims to empower individuals by simplifying credit report review and the exercise of consumer rights.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### UI/UX Decisions
The application utilizes Streamlit with a wide layout and a **full-screen stepper component** UX. A sticky stepper bar at the top shows the 6-step pipeline: **Upload → Review → Letters → Proof → Mail → Track**. Each step lights up gold when active, turns green with a checkmark when completed, and stays dimmed when upcoming. The stepper resets per dispute round (Round 1, Round 2, etc.). The stepper component is in `ui/stepper.py`. The underlying state machine uses `st.session_state.ui_card` for the intake flow and `st.session_state.panel` for post-intake panels. Mobile-first design with a charcoal palette and gold/amber accents. Blob-based `components.html()` buttons are used for all downloads to ensure mobile compatibility.

### Technical Implementations

#### Core Functionality
- **PDF Parsing**: Extracts text from PDFs using `pdfplumber` and `pytesseract` (OCR fallback), supporting multi-bureau reports (Equifax, Experian, TransUnion).
- **Statutes Module & Legal Knowledge Base**: Defines dispute-relevant statutes and provides structured legal data (FCRA, Dodd-Frank, TILA) for AI strategy.
- **Claim Extraction & ReviewClaim Compression**: Processes claims into human-reviewable "ReviewClaims" based on canonical rules and categorizes them, supported by a "Truth Sheet System."
- **Letter Generator**: Creates bureau-specific dispute letters for Round 1 (No-Proof) and Round 2+ (Verification-Demand) modes, including date-aware concern generation.
- **AI Dispute Strategy**: A tiered system providing AI-powered strategy recommendations with an LLM layer for reasoning under legal guardrails.
- **Multi-Bureau Aggregation**: Performs cross-bureau deduplication, name normalization, account matching, and discrepancy detection for a unified summary.
- **AI-Enhanced Analysis Layer**: Provides a secondary AI pass for deeper insights and quick wins from parsed credit report data.
- **Authentication & Entitlement System**: Custom bcrypt-hashed authentication with PostgreSQL-backed sessions, supporting roles, email verification, and an entitlement-based business model with a free tier and a "Founding Member Program."
- **Voice Profile System**: Allows users to customize the tone, detail, and closing phrases of generated dispute letters.
- **Signature Pad**: HTML5 Canvas-based signature drawing pad (`ui/signature_pad.py`) with touch/mobile support. Signatures stored in `user_signatures` table (BYTEA) and embedded into dispute letter PDFs via `generate_letter_pdf(signature_image=...)` in `letter_generator.py`. Integrated into the VOICE_PROFILE card before letter generation. Users can draw, redraw, or skip.
- **Round 2+ Before/After Comparison**: Compares updated credit reports with previous snapshots of disputed items.
- **Strike Metrics & War Room**: Calculates 20 key credit profile metrics to determine a `primary_lever` and generates a dynamic action plan via the "War Room" UI.
- **Bureau Investigation Tracker**: A dashboard displaying dispute status, countdown timers, and expected outcomes.
- **Letter Bank**: User-facing panel showing all generated dispute letters grouped by round, with individual PDF downloads (signed + proof docs attached) and a "Download All" ZIP option. Accessible from the home nav bar.
- **Admin Letter Management**: Admins can view, download, and mail any user's letters from the user detail view in the admin dashboard. Letters are generated as PDFs with the user's signature and proof documents attached. Admins can send letters via Lob certified mail on behalf of users.
- **Escalation Panel**: Tools for post-30-day escalation, including MOV letters, CFPB complaints, and Executive Escalation letters.
- **Evidence Tracker**: A tool for users to log evidence for Round 2 escalation across various categories.
- **Nudge Rules Engine**: A rule-based engine for delivering actionable, contextual nudges to users.
- **Share Your Win Card & Social Referral**: Encourages social sharing of results with referral codes after successful mailings.
- **LETTERS_READY → Proof → Mail Pipeline**: A structured 4-step pipeline for letter processing, document uploads, mailing, and tracking.
- **Proof Document Upload & Gating**: Secure upload page for government ID and proof of address, gating letter downloads and certified mail sending until documents are provided. Uploaded ID and proof of address images are appended as additional pages at the end of each generated letter PDF via `generate_letter_pdf(proof_documents=...)`, so downloaded/mailed letters are self-contained with all enclosures. AI-powered document validation (`doc_validator.py`) checks uploaded files via OpenAI vision to verify they look like the correct document type before saving; graceful fallback if validation is unavailable.
- **Lob Letter Status Polling**: Background polling for tracking certified mail delivery status via Lob API.
- **Session Persistence**: Three-layer session recovery (cookies, URL params, DB-backed device fingerprinting) with UI state persistence. Includes fallback letter restoration: when a returning user has no saved `ui_card` but has letters in the DB, the init logic restores `generated_letters` from DB and advances to the DONE card (routing to documents panel if proof docs are missing).
- **Stripe Integration**: Idempotent payment processing and reconciliation for purchases and entitlements.
- **Privacy & Security**: Features privacy consent, cookie banners, user-scoped data, a "Delete All My Data" feature, and security hardening measures like rate limiting and webhook validation.
- **Database Layer**: PostgreSQL database with `psycopg2.pool.ThreadedConnectionPool` for application data storage.
- **Ad Landing Page & Conversion Tracking**: Dedicated landing page for paid traffic with Meta and TikTok Pixel integration and UTM attribution.
- **Magic Upload Link**: Generates a secure, 7-day tokenized URL (`?upload=<token>`) that lets users upload proof documents (ID + address) without logging in. Tokens are stored in `upload_tokens` table, validated via `validate_upload_token()`, and scoped to a single user_id. Auto-emailed after letter generation via `send_upload_link_email()` in `resend_client.py`. Copyable link shown on LETTERS_READY card and DONE home panel when docs are missing.
- **Demo Mode ("Try It Now")**: Unauthenticated visitors can experience a sample credit report analysis flow without signing up. Activated via `?nav=demo` from the landing page "Try It Now" button. Loads pre-built sample data for fictional "Alex Johnson" (8 accounts, 6 dispute items across TransUnion). Users see Summary → Disputes → Sample Letter Preview. All DB/auth/Stripe calls are guarded with `_is_demo` flag (`st.session_state._demo_mode`). Sidebar is hidden via CSS. A persistent gold demo banner shows "Sign Up Free" and "Exit Demo" links. The generate button is replaced with "Preview Sample Letter" showing a static HTML letter. Demo state is fully cleaned up on exit. Key files: `demo_data.py` (sample data + letter HTML), `app.py` (routing + guards), `views/landing.py` (CTA button), `ui/css.py` (`lp-btn-demo` ghost style).
- **Landing Page Scroll Animations**: IntersectionObserver-based fade-in animations on `.lp-section` elements. Adds `.lp-animate` class on load and `.lp-visible` on scroll into view. Respects `prefers-reduced-motion`. Script injected via `components.html()` at end of `render_landing_page()`.
- **Credit Report Resource Guide**: Accordion-style resource guide section on landing page replacing the old compact "Need your credit report?" block. AnnualCreditReport.com shown as featured/recommended card, with 5 more sources (Equifax, Experian, TransUnion, Credit Karma, bank/credit card) behind a collapsible "See more options" `<details>` toggle. Uses `.lp-guide-*` CSS classes.

## External Dependencies

### Python Libraries
- `streamlit`: Web application UI
- `pdfplumber`: Native PDF text extraction
- `pdf2image`: PDF to image conversion
- `pytesseract`: Optical Character Recognition (OCR)
- `pandas`: Data manipulation
- `psycopg2-binary`: PostgreSQL connectivity
- `reportlab`: PDF document generation
- `openai`: AI-powered dispute strategy

### System Requirements
- Tesseract OCR engine
- Poppler utilities
- PostgreSQL database server

### Third-Party Services
- Resend API (for email services)
- Stripe API (for payment processing)
- Lob API (for Certified Mail integration)

### Mission Control (React) + Workflow API on Replit
- **Deployed Repl (Autoscale)** runs `scripts/replit_deployment_entry.sh`: FastAPI `api.workflow_app` on **port 8000** and Streamlit on **port 5000**. The published webview is still Streamlit; the React app is not part of that run command.
- **Developing Mission Control**: use the **Project** Run button (parallel workflows) or start both manually: `streamlit …` on 5000 and `python -m uvicorn api.workflow_app:app --host 0.0.0.0 --port 8000` on 8000. From the Shell, run `cd web && npm install && npm run dev` so Vite serves the React app (default **5173**, bound to `0.0.0.0`). Mission Control uses `/workflow-api` → Vite proxy → `127.0.0.1:8000` unless overridden.
- **Secrets / env**: set `WORKFLOW_ADMIN_API_SECRET` for admin routes; optional `WORKFLOW_INTERNAL_API_SECRET` for worker/internal endpoints. For Mission Control UI, operators paste the same value (or use `VITE_WORKFLOW_ADMIN_KEY` only for local convenience — prefer Secrets for real admin keys).
- **Cross-origin**: if the browser origin is not the Vite dev server (e.g. `vite preview`), set `VITE_WORKFLOW_API_URL` to the full origin of the workflow API (Replit’s URL for port **8000**). Optional `WORKFLOW_API_PROXY_TARGET` adjusts the dev proxy target (default `http://127.0.0.1:8000`).

## Replit handoff checklist

### Runtime contract (verify after pull)
| Service | Port | Bind | Notes |
|---------|------|------|--------|
| Streamlit (`app.py`) | **5000** | `0.0.0.0` | Primary webview; `.streamlit/config.toml` also sets 5000 |
| Workflow API (`api.workflow_app`) | **8000** | `0.0.0.0` | Same Repl as Streamlit for dev proxy |
| Vite (Mission Control / React) | **5173** | `0.0.0.0` | `web/vite.config.ts` proxies `/workflow-api` → `WORKFLOW_API_PROXY_TARGET` or `http://127.0.0.1:8000` |

### Autoscale **Run** (production deploy)
- Command: `scripts/replit_deployment_entry.sh`.
- **Does not depend on git-updated `.replit`:** templates often map **public port 80 → local 5000**. The script **`exec`’s uvicorn on 5000** (customer React + `/api/...`) and runs **Streamlit on 5001** in the background (open **5001** from Replit **Ports** for the legacy UI).
- **Customer React** when `web/dist` exists: main deploy URL → SPA at `/`. API accepts **`/workflow-api/...`** (stripped) for bundled `web/dist`.
- After `git pull`, if needed: `cd web && npm install && npm run build` (or use committed `web/dist`).

### Dev: Mission Control (same Repl)
1. Start API + Streamlit: use the **Project** workflow in `.replit` (parallel **streamlit_app** + **workflow_api**) *or* run the same two commands from the Shell.
2. In another Shell: `cd web && npm install && npm run dev`
3. Open the Replit preview URL for port **5173**, then navigate to **`/mission-control`** (e.g. `https://<your-5173-preview-host>/mission-control`).
4. Paste **Workflow Admin** secret in the UI (or set `VITE_WORKFLOW_ADMIN_KEY` only for local convenience; prefer Replit **Secrets** for real keys).

### Required / recommended Secrets (Streamlit + API)
- **`DATABASE_URL`** — **required** (`app.py` stops without it). Use Replit PostgreSQL.
- **`WORKFLOW_ADMIN_API_SECRET`** — required for `/internal/admin/...` and Mission Control actions.
- **`WORKFLOW_INTERNAL_API_SECRET`** — optional but needed for internal/worker routes and some automation.
- **Recommended:** `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `LOB_API_KEY` (app warns if missing).
- **Email:** `RESEND_API_KEY`; `RESEND_FROM_EMAIL` optional (`.replit` sets a shared default for userenv).
- **AI:** `AI_INTEGRATIONS_OPENAI_API_KEY` (and optional `AI_INTEGRATIONS_OPENAI_BASE_URL`) for strategy / doc validation paths.

### Public interactive demo (`/demo` on customer React)
Ships with the repo as long as **`samples/*.pdf`** is in the deployment tree (same paths as `services/public_demo_service.py`).

- **`PUBLIC_DEMO_ENABLED=1`** — turns on `GET/POST /api/public/demo/*`.
- **`PUBLIC_DEMO_USER_ID=<users.id>`** — dedicated account used only for fixture runs (visitors never log in as this user).
- Run once after picking the user id: `python scripts/bootstrap_public_demo_user.py <id>` (grants letter/mail credits from the API host).
- Optional **`PUBLIC_DEMO_SECRET`** — if set, the browser must send `X-Public-Demo-Secret`; set matching **`VITE_PUBLIC_DEMO_SECRET`** in `web/.env.local` and rebuild `web/dist`.
- Optional **`DEMO_LEADS_NOTIFY_EMAIL`** — Resend ping when someone submits the demo lead form.
- Validate before launch: `PUBLIC_DEMO_ENABLED=1` + `WORKFLOW_LAUNCH_VALIDATE_DB=1 python scripts/workflow_launch_validate.py` (checks user exists + fixtures on disk).

### Build note
- `.replit` **deployment** `build` uses an explicit `pip install …` list, not `requirements.txt`. Keep it in sync with imports or switch the build step to `pip install -r requirements.txt` (note: `requirements.txt` includes **playwright**, which is heavy on Repl builds).