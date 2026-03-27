/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Full origin of workflow FastAPI (no path), e.g. https://repl-8000.replit.dev */
  readonly VITE_WORKFLOW_API_URL?: string;
  readonly VITE_WORKFLOW_API_PREFIX?: string;
  readonly VITE_WORKFLOW_ADMIN_KEY?: string;
  /** Dev-only: same bearer Streamlit stores in `auth_token` cookie after login */
  readonly VITE_SESSION_BEARER_TOKEN?: string;
  /** Override IdentityIQ / MyScoreIQ affiliate landing (default set in reportAcquisitionConfig). */
  readonly VITE_IDIQ_REPORT_URL?: string;
  /** Override free annual report site URL (default annualcreditreport.com). */
  readonly VITE_ANNUAL_CREDIT_REPORT_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
